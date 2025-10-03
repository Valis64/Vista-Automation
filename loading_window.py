"""Progress/Loading window used while Illustrator processes pairs."""

from __future__ import annotations

import re
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
import tkinter.font as tkfont
from pathlib import Path
import json
import sys

if getattr(sys, "frozen", False):
    APP_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    APP_DIR = Path(__file__).resolve().parent
TEMPLATE_SETTINGS_DIR = APP_DIR / "template_settings"
PAUSE_FILE = "jsx_pause.flag"
CANCEL_FILE = "jsx_cancel.flag"

PAPER_TYPE_RE = re.compile(r"(\d+in)", re.IGNORECASE)

from utils.common import (
    LAM_COLORS,
    get_laminate_color,
    load_template_settings,
    is_coffee_sleeve,
    is_pb001,
    is_pb005,
)


class LoadingWindow:
    """UI window to show progress while Illustrator runs."""

    def __init__(self, parent: tk.Tk | tk.Toplevel, items: list[dict], pair_orders: list[str]):
        self.parent = parent
        self.items = items
        self.pair_orders = pair_orders

        self.window = tk.Toplevel(parent)
        self.window.title("Please Wait")
        self.window.attributes("-topmost", True)
        self.window.after(1000, lambda: self.window.attributes("-topmost", False))

        self.pair_window: tk.Toplevel | None = None

        try:
            big_font = tkfont.nametofont("TkDefaultFont").copy()
            big_font.configure(size=big_font.cget("size") + 3)
            self.window.option_add("*Font", big_font)
        except Exception:
            pass

        # Track templates without settings already prompted to avoid repeats
        self.missing_settings: set[str] = set()
        self.pair_rows: dict[int, str] = {}
        self.pair_row_labels: dict[int, str] = {}
        self.pair_row_display: dict[int, str] = {}
        self.pair_row_papers: dict[int, str] = {}
        self.row_to_pair: dict[str, int] = {}
        self.completed_pairs: set[int] = set()

        self.show_pair_window()

        style = ttk.Style(self.window)
        style.configure("LargePB.Horizontal.TProgressbar", thickness=20, troughcolor="#eee")

        self.summary_var = tk.StringVar(value="Steps processed: 0")
        self.pair_var = tk.StringVar(value="Order N/A - Pair N/A")
        self.status_var = tk.StringVar(value="Starting Illustrator...")

        ttk.Label(self.window, textvariable=self.status_var).pack(padx=20, pady=(5, 5))

        info_frame = tk.Frame(self.window, bg="black")
        info_frame.pack(padx=20, pady=(0, 10))

        self.order_disp_var = tk.StringVar()
        self.pair_disp_var = tk.StringVar()
        self.company_disp_var = tk.StringVar()
        self.setting_disp_var = tk.StringVar()
        fields = [
            ("Steps", self.summary_var, 20, None),
            ("Current", self.pair_var, 25, None),
            ("Order ID", self.order_disp_var, 15, None),
            ("Pair", self.pair_disp_var, 10, None),
            ("Company", self.company_disp_var, 30, None),
            ("Setting", self.setting_disp_var, 20, "setting_entry"),
        ]

        for i, (lbl, var, width, attr) in enumerate(fields):
            row, col = divmod(i, 3)
            box = tk.Frame(info_frame, bg="black", bd=2, relief="raised")
            box.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            tk.Label(box, text=lbl, bg="black", fg="#00FF00").pack(anchor="w")
            entry = tk.Entry(
                box,
                textvariable=var,
                state="readonly",
                width=width,
                fg="#00FF00",
                readonlybackground="black",
                relief="flat",
                highlightthickness=0,
                insertbackground="#00FF00",
            )
            entry.pack()
            if attr:
                setattr(self, attr, entry)

        logs_frame = ttk.Frame(self.window)
        logs_frame.pack(padx=20, pady=(0, 10), fill="both", expand=True)

        self.log_box = scrolledtext.ScrolledText(
            logs_frame,
            width=80,
            height=40,
            state="disabled",
            background="black",
            foreground="#00FF00",
            font=("Courier New", 12),
        )
        self.art_log = scrolledtext.ScrolledText(
            logs_frame,
            width=40,
            height=20,
            state="disabled",
            background="black",
            foreground="#00FF00",
            font=("Courier New", 12),
        )
        self.template_log = scrolledtext.ScrolledText(
            logs_frame,
            width=40,
            height=20,
            state="disabled",
            background="black",
            foreground="#00FF00",
            font=("Courier New", 12),
        )
        self.verbose_autoscroll = tk.BooleanVar(value=True)

        notebook = ttk.Notebook(logs_frame)
        notebook.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(5, 0))

        pair_log_tab = ttk.Frame(notebook)
        pair_log_tab.columnconfigure(0, weight=1)
        pair_log_tab.rowconfigure(0, weight=1)
        verbose_log_tab = ttk.Frame(notebook)
        verbose_log_tab.columnconfigure(0, weight=1)
        verbose_log_tab.rowconfigure(1, weight=1)

        self.pair_log = scrolledtext.ScrolledText(
            pair_log_tab,
            width=40,
            height=5,
            state="disabled",
            background="black",
            foreground="#00FF00",
            font=("Courier New", 12),
        )
        self.pair_log.grid(row=0, column=0, sticky="nsew")

        control_bar = ttk.Frame(verbose_log_tab)
        control_bar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Button(control_bar, text="Clear", command=self.clear_verbose_log).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(control_bar, text="Save", command=self.save_verbose_log).pack(
            side="left", padx=(0, 5)
        )
        ttk.Checkbutton(
            control_bar,
            text="Auto-scroll",
            variable=self.verbose_autoscroll,
            command=self._maybe_scroll_verbose,
        ).pack(side="left")

        self.verbose_log = scrolledtext.ScrolledText(
            verbose_log_tab,
            width=40,
            height=20,
            state="disabled",
            background="black",
            foreground="#00FF00",
            font=("Courier New", 12),
        )
        self.verbose_log.grid(row=1, column=0, sticky="nsew")

        notebook.add(pair_log_tab, text="Pair Log")
        notebook.add(verbose_log_tab, text="Verbose Log")

        for box in (self.log_box, self.art_log, self.template_log, self.verbose_log, self.pair_log):
            box.tag_config(
                "timestamp",
                foreground="yellow",
                font=("Courier New", 11, "italic"),
            )

        self.log_box.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.art_log.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.template_log.grid(row=1, column=1, sticky="nsew", padx=(5, 0))

        logs_frame.columnconfigure(0, weight=3)
        logs_frame.columnconfigure(1, weight=1)
        logs_frame.rowconfigure(0, weight=1)
        logs_frame.rowconfigure(1, weight=1)
        logs_frame.rowconfigure(2, weight=0)

        self.pb = ttk.Progressbar(
            self.window,
            mode="indeterminate",
            length=350,
            style="LargePB.Horizontal.TProgressbar",
        )
        self.pb.pack(padx=20, pady=15)
        self.pb.start()

        self.apm_var = tk.DoubleVar(value=0)
        self.apm_label_var = tk.StringVar(value="APM: 0.0")
        self.apm_bar = ttk.Progressbar(
            self.window,
            mode="determinate",
            length=350,
            style="LargePB.Horizontal.TProgressbar",
            maximum=60,
            variable=self.apm_var,
        )
        self.apm_bar.pack(padx=20, pady=(0, 5))
        ttk.Label(self.window, textvariable=self.apm_label_var).pack(padx=20, pady=(0, 5))

        self.elapsed_var = tk.StringVar(value="Total: 0s")
        self.pair_elapsed_var = tk.StringVar(value="Pair: 0s")
        ttk.Label(self.window, textvariable=self.elapsed_var).pack(padx=20, pady=(0, 0))
        ttk.Label(self.window, textvariable=self.pair_elapsed_var).pack(padx=20, pady=(0, 10))

        btn_frame = tk.Frame(self.window)
        btn_frame.pack(pady=(0, 10))
        self.pause_btn = ttk.Button(btn_frame, text="Pause", command=self.toggle_pause)
        self.pause_btn.pack(side="left", padx=5)
        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.cancel)
        self.cancel_btn.pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Pairs Window", command=self.show_pair_window).pack(
            side="left", padx=5
        )

        self.paused = False

        self.step_count = 0
        self.current_pair = -1
        self.start_time: float | None = None
        self.pair_start_times: dict[int, float] = {}

        # Periodically update timer labels
        self.window.after(1000, self.update_timers)

        self.window.update_idletasks()

        try:
            parent_width = parent.winfo_width()
            parent_height = parent.winfo_height()
        except Exception:
            parent_width = parent_height = 0

        requested_width = self.window.winfo_reqwidth()
        requested_height = self.window.winfo_reqheight()

        width = max(requested_width, parent_width)
        height = max(requested_height, parent_height)

        padding = 40
        screen_height = self.window.winfo_screenheight()
        available_height = max(screen_height - padding, 1)
        height = min(height, available_height)

        min_width = min(requested_width, width) if requested_width else width
        min_height = min(requested_height, height) if requested_height else height

        self.window.geometry(f"{width}x{height}")
        self.window.minsize(min_width, min_height)
        self.window.resizable(True, True)

    def close(self):
        self.pb.stop()
        self.window.destroy()
        if self._pair_window_exists():
            try:
                self.pair_window.deiconify()
                self.pair_window.lift()
                self.pair_window.focus_force()
            except Exception:
                pass

    def toggle_pause(self):
        flag = APP_DIR / PAUSE_FILE
        if self.paused:
            try:
                flag.unlink()
            except Exception:
                pass
            self.pb.start()
            self.pause_btn.config(text="Pause")
            self.paused = False
        else:
            try:
                flag.touch()
            except Exception:
                pass
            self.pb.stop()
            self.pause_btn.config(text="Resume")
            self.paused = True

    def cancel(self):
        try:
            (APP_DIR / CANCEL_FILE).touch()
        except Exception:
            pass
        self.cancel_btn.config(state="disabled")
        self.pause_btn.config(state="disabled")
        self.update_status("Cancelling...")

    def clear_verbose_log(self):
        self.verbose_log.config(state="normal")
        self.verbose_log.delete("1.0", tk.END)
        self.verbose_log.config(state="disabled")

    def save_verbose_log(self):
        path = filedialog.asksaveasfilename(
            parent=self.window,
            defaultextension=".txt",
            filetypes=(("Text Files", "*.txt"), ("All Files", "*.*")),
        )
        if not path:
            return
        try:
            content = self.verbose_log.get("1.0", tk.END)
            Path(path).write_text(content, encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc), parent=self.window)

    def _maybe_scroll_verbose(self):
        if self.verbose_autoscroll.get():
            self.verbose_log.see(tk.END)

    def _mark_pair_complete(self, pair_idx: int) -> None:
        iid = self.pair_rows.get(pair_idx)
        if iid is None:
            return
        tree = self.orders_tree if self._pair_window_exists() else None
        if pair_idx in self.completed_pairs and self.pair_row_display.get(pair_idx, "").endswith("✓"):
            if tree is not None:
                tags = [tag for tag in tree.item(iid, "tags") or () if tag != "pending"]
                if "done" not in tags:
                    tags.append("done")
                tree.item(iid, tags=tags)
            return
        base_text = self.pair_row_labels.get(pair_idx)
        if base_text is None:
            values = tree.item(iid, "values") if tree is not None else ()
            base_text = values[0] if values else ""
            self.pair_row_labels[pair_idx] = base_text
        display_text = self.pair_row_display.get(pair_idx, base_text or "")
        if not display_text.endswith("✓"):
            display_text = f"{base_text or ''} ✓"
        paper = self.pair_row_papers.get(pair_idx)
        if paper is None:
            values = tree.item(iid, "values") if tree is not None else ()
            paper = values[1] if len(values) > 1 else ""
            self.pair_row_papers[pair_idx] = paper
        if tree is not None:
            tags = [tag for tag in tree.item(iid, "tags") or () if tag != "pending"]
            if "done" not in tags:
                tags.append("done")
            tree.item(iid, values=(display_text, paper), tags=tags)
        self.pair_row_display[pair_idx] = display_text
        self.completed_pairs.add(pair_idx)

    def update_timers(self):
        if self.start_time is not None:
            elapsed = time.time() - self.start_time
            self.elapsed_var.set(f"Total: {int(elapsed)}s")
            if self.current_pair in self.pair_start_times:
                cur_elapsed = time.time() - self.pair_start_times[self.current_pair]
                self.pair_elapsed_var.set(f"Pair: {int(cur_elapsed)}s")
            else:
                self.pair_elapsed_var.set("Pair: 0s")
            apm = (self.step_count * 60 / elapsed) if elapsed else 0.0
            self.apm_var.set(min(apm, self.apm_bar["maximum"]))
            self.apm_label_var.set(f"APM: {apm:.1f}")
        self.window.after(1000, self.update_timers)

    def _append(
        self,
        box: scrolledtext.ScrolledText,
        text: str | None = None,
        tag: str | None = None,
        extra_space: bool = False,
        *,
        auto_scroll: bool = True,
    ):
        box.config(state="normal")
        ts = time.strftime("[%H:%M:%S] ")
        box.insert(tk.END, ts, "timestamp")
        if tag:
            box.insert(tk.END, (text or self.status_var.get()) + "\n", tag)
        else:
            box.insert(tk.END, (text or self.status_var.get()) + "\n")
        if extra_space:
            box.insert(tk.END, "\n")
        if auto_scroll:
            box.see(tk.END)
        box.config(state="disabled")

    def update_status(self, msg: str):
        if self.start_time is None:
            self.start_time = time.time()
        m = re.search(r"pair\s+(\d+)(?:\s+of\s+(\d+))?", msg, re.I)
        duration = None
        if m:
            pair_idx = int(m.group(1)) - 1
            total = m.group(2) or len(self.pair_orders)
            low_msg = msg.lower()
            if "processing" in low_msg or self.current_pair == -1:
                self.current_pair = pair_idx
                self.pair_start_times[pair_idx] = time.time()
            if "finished" in low_msg and pair_idx in self.pair_start_times:
                duration = time.time() - self.pair_start_times.pop(pair_idx)
                msg += f" ({duration:.1f}s)"
            if 0 <= pair_idx < len(self.pair_orders):
                self.pair_var.set(
                    f"Order {self.pair_orders[pair_idx]} - Pair {pair_idx + 1} of {total}"
                )
                self.order_disp_var.set(self.pair_orders[pair_idx])
                self.pair_disp_var.set(f"{pair_idx + 1} / {total}")
                self.company_disp_var.set(self.items[pair_idx].get("company", ""))
                if "finished" in low_msg:
                    self._mark_pair_complete(pair_idx)
        prefix = ""
        if 0 <= self.current_pair < len(self.pair_orders):
            prefix = f"Order {self.pair_orders[self.current_pair]} - "
        self.step_count += 1
        self.summary_var.set(f"Steps processed: {self.step_count}")
        elapsed = time.time() - self.start_time
        apm = (self.step_count * 60 / elapsed) if elapsed else 0.0
        self.apm_var.set(min(apm, self.apm_bar["maximum"]))
        self.apm_label_var.set(f"APM: {apm:.1f}")
        self.elapsed_var.set(f"Total: {int(elapsed)}s")
        if self.current_pair in self.pair_start_times:
            cur_elapsed = time.time() - self.pair_start_times[self.current_pair]
            self.pair_elapsed_var.set(f"Pair: {int(cur_elapsed)}s")
        else:
            self.pair_elapsed_var.set("Pair: 0s")
        self.status_var.set(prefix + msg)

        lower = msg.lower()
        if self.current_pair >= 0 and "saved" in lower and "flat" in lower:
            paper = self._extract_paper_type(msg)
            if paper:
                self._set_pair_paper(self.current_pair, paper)
        auto_kwargs = {"auto_scroll": self.verbose_autoscroll.get()}
        self._append(self.log_box)
        if msg.startswith("  "):
            self._append(self.verbose_log, **auto_kwargs)
            self._append(self.verbose_log, msg.strip(), extra_space=True, **auto_kwargs)
        elif m:
            self._append(self.verbose_log, **auto_kwargs)
            lam = self.items[pair_idx].get("lamType", "")
            color = get_laminate_color(lam)
            tag = f"lam_{color}"
            if not self.pair_log.tag_cget(tag, "foreground"):
                self.pair_log.tag_config(tag, foreground=color)
                self.verbose_log.tag_config(tag, foreground=color)
            prefix_msg = "✔" if "finished" in lower else "→"
            entry = f"{prefix_msg} {self.pair_var.get()}"
            details = (f" - {lam}" if lam else "")
            specials = []
            tmpl_code = self.items[pair_idx].get("template", "")
            settings = load_template_settings(tmpl_code)
            if not settings and tmpl_code and tmpl_code not in self.missing_settings:
                self.missing_settings.add(tmpl_code)
                if messagebox.askyesno(
                    "Missing Template Settings",
                    f"No settings found for {tmpl_code}. Create now?",
                    parent=self.window,
                ):
                    self._append(
                        self.log_box,
                        f"Opened template settings editor for {tmpl_code}",
                    )
                    try:
                        self.parent.open_template_settings_editor(tmpl_code)
                    except Exception as exc:
                        messagebox.showerror("Error", str(exc), parent=self.window)
                else:
                    self._append(
                        self.log_box,
                        f"Skipped creating settings for {tmpl_code}",
                    )
            self.setting_disp_var.set(tmpl_code)
            color = "#FF00FF" if settings else "#00FF00"
            self.setting_entry.config(
                foreground=color,
                disabledforeground=color,
                insertbackground=color,
            )
            if is_coffee_sleeve(tmpl_code):
                specials.append("Coffee Sleeve")
            if settings.get("bleedPaths") and len(settings["bleedPaths"]) > 1 and not is_coffee_sleeve(tmpl_code):
                specials.append(f"{len(settings['bleedPaths'])}up")
            elif is_pb001(tmpl_code):
                specials.append("2up")
            rot = settings.get("rotation")
            if rot == 180 or is_pb005(tmpl_code):
                specials.append("180°")
            elif rot == 90 and not is_coffee_sleeve(tmpl_code):
                specials.append("90°")
            if specials:
                details += f" ({', '.join(specials)})"
            time_note = f" ({duration:.1f}s)" if duration is not None else ""
            self._append(self.pair_log, entry + details + time_note, tag)
            self._append(
                self.verbose_log,
                entry + details + time_note,
                tag,
                extra_space=True,
                **auto_kwargs,
            )
        else:
            self._append(self.verbose_log, extra_space=True, **auto_kwargs)
            if "art" in lower:
                self._append(self.art_log)
            if "template" in lower:
                self._append(self.template_log)

    def _extract_paper_type(self, text: str) -> str:
        match = PAPER_TYPE_RE.search(text)
        return match.group(1).lower() if match else ""

    def _set_pair_paper(self, pair_idx: int, paper: str) -> None:
        if not paper:
            return
        if not (0 <= pair_idx < len(self.pair_orders)):
            return
        iid = self.pair_rows.get(pair_idx)
        if iid is None:
            return
        tree = self.orders_tree if self._pair_window_exists() else None
        current = (self.pair_row_papers.get(pair_idx) or "").strip()
        paper = paper.strip()
        if current == paper:
            return
        display_text = self.pair_row_display.get(pair_idx)
        if display_text is None:
            values = tree.item(iid, "values") if tree is not None else ()
            display_text = values[0] if values else ""
            self.pair_row_display[pair_idx] = display_text
        if tree is not None:
            tags = tree.item(iid, "tags")
            tree.item(iid, values=(display_text, paper), tags=tags)
        self.pair_row_papers[pair_idx] = paper
        try:
            self.items[pair_idx]["paperType"] = paper
        except Exception:
            pass

    def _prompt_manual_paper_type(self, event: tk.Event | None = None):
        tree = self.orders_tree if self._pair_window_exists() else None
        if tree is None:
            return "break"
        iid = tree.focus()
        if not iid:
            selection = tree.selection()
            iid = selection[0] if selection else ""
        if not iid:
            return "break"
        pair_idx = self.row_to_pair.get(iid)
        if pair_idx is None:
            for idx, row_iid in self.pair_rows.items():
                if row_iid == iid:
                    pair_idx = idx
                    self.row_to_pair[iid] = idx
                    break
        if pair_idx is None:
            return "break"
        label = self.pair_row_labels.get(pair_idx, f"Pair {pair_idx + 1}")
        current = self.pair_row_papers.get(pair_idx, "")
        parent_window = self.pair_window if self._pair_window_exists() else self.window
        response = simpledialog.askstring(
            "Paper Type",
            f"Enter paper type for {label}",
            initialvalue=current,
            parent=parent_window,
        )
        if response is None:
            return "break"
        response = response.strip()
        if not response:
            return "break"
        self._set_pair_paper(pair_idx, response)
        return "break"

    def show_pair_window(self):
        if self._pair_window_exists():
            try:
                self.pair_window.deiconify()
                self.pair_window.lift()
                self.pair_window.focus_force()
            except Exception:
                pass
            return
        self._create_pair_table_window()

    def _pair_window_exists(self) -> bool:
        return bool(self.pair_window) and bool(self.pair_window.winfo_exists())

    def _create_pair_table_window(self):
        self.pair_window = tk.Toplevel(self.parent)
        self.pair_window.title("Pairs & Paper Types")
        self.pair_window.attributes("-topmost", True)
        self.pair_window.after(1000, lambda: self.pair_window.attributes("-topmost", False))

        container = ttk.Frame(self.pair_window, padding=10)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Pairs & Paper Types").pack(anchor="center", pady=(0, 5))

        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill="both", expand=True)

        tree_height = min(5, max(len(self.pair_orders), 1))
        self.orders_tree = ttk.Treeview(
            tree_frame,
            columns=("pair", "paper"),
            show="headings",
            height=tree_height,
            selectmode="browse",
        )
        self.orders_tree.heading("pair", text="Pair", anchor="center")
        self.orders_tree.heading("paper", text="Paper Type", anchor="center")
        self.orders_tree.column("pair", anchor="center", width=260, stretch=True)
        self.orders_tree.column("paper", anchor="center", width=180, stretch=True)
        self.orders_tree.pack(side="left", fill="both", expand=True)

        orders_scroll = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.orders_tree.yview
        )
        orders_scroll.pack(side="right", fill="y")
        self.orders_tree.configure(yscrollcommand=orders_scroll.set)

        instruction = ttk.Label(
            container,
            text="Double-click or press Enter to update the selected paper type.",
            wraplength=360,
        )
        instruction.pack(anchor="w", pady=(5, 0))

        self.orders_tree.tag_configure("pending", background="black", foreground="#FF0000")
        done_font = None
        try:
            done_font = tkfont.nametofont("TkDefaultFont").copy()
        except Exception:
            done_font = None
        self._tree_done_font = done_font
        done_tag_style: dict[str, object] = {"foreground": "#228B22"}
        if done_font is not None:
            done_tag_style["font"] = done_font
        self.orders_tree.tag_configure("done", **done_tag_style)

        self.orders_tree.delete(*self.orders_tree.get_children())
        self.pair_rows.clear()
        self.row_to_pair.clear()

        for idx, order_id in enumerate(self.pair_orders):
            item = self.items[idx] if idx < len(self.items) else {}
            paper = self.pair_row_papers.get(idx)
            if paper is None:
                paper = item.get("paperType", "")
            pair_label = f"{idx + 1}. {order_id}"
            self.pair_row_labels[idx] = pair_label
            self.pair_row_display[idx] = pair_label
            self.pair_row_papers[idx] = paper
            iid = self.orders_tree.insert(
                "",
                "end",
                values=(pair_label, paper),
                tags=("pending",),
            )
            self.pair_rows[idx] = iid
            self.row_to_pair[iid] = idx

        for idx in sorted(self.completed_pairs):
            self._mark_pair_complete(idx)

        self.orders_tree.bind("<Double-1>", self._prompt_manual_paper_type)
        self.orders_tree.bind("<Return>", self._prompt_manual_paper_type)
        self.orders_tree.bind("<KP_Enter>", self._prompt_manual_paper_type)
        self.pair_window.bind(
            "<Destroy>",
            lambda event: self._on_pair_window_destroy(event) if event.widget is self.pair_window else None,
        )

    def _on_pair_window_destroy(self, event: tk.Event):
        self.pair_window = None
        self.orders_tree = None
