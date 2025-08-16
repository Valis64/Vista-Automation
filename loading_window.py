"""Progress/Loading window used while Illustrator processes pairs."""

from __future__ import annotations

import re
import time
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
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

        try:
            big_font = tkfont.nametofont("TkDefaultFont").copy()
            big_font.configure(size=big_font.cget("size") + 3)
            self.window.option_add("*Font", big_font)
        except Exception:
            pass

        try:
            width = parent.winfo_width()
            height = parent.winfo_height()
        except Exception:
            width = height = 0
        if width and height:
            self.window.geometry(f"{width}x{height}")
        self.window.resizable(False, False)

        # Track templates without settings already prompted to avoid repeats
        self.missing_settings: set[str] = set()

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
        self.detail_log = scrolledtext.ScrolledText(
            logs_frame,
            width=40,
            height=20,
            state="disabled",
            background="black",
            foreground="#00FF00",
            font=("Courier New", 12),
        )
        self.pair_log = scrolledtext.ScrolledText(
            logs_frame,
            width=40,
            height=5,
            state="disabled",
            background="black",
            foreground="#00FF00",
            font=("Courier New", 12),
        )
        for box in (self.log_box, self.art_log, self.template_log, self.detail_log, self.pair_log):
            box.tag_config(
                "timestamp",
                foreground="yellow",
                font=("Courier New", 11, "italic"),
            )

        self.log_box.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.art_log.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.template_log.grid(row=1, column=1, sticky="nsew", padx=(5, 0))
        self.detail_log.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(5, 0))
        self.pair_log.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(5, 0))

        logs_frame.columnconfigure(0, weight=3)
        logs_frame.columnconfigure(1, weight=1)
        logs_frame.columnconfigure(2, weight=1)
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

        self.paused = False

        self.step_count = 0
        self.current_pair = -1
        self.start_time: float | None = None
        self.pair_start_times: dict[int, float] = {}

        # Periodically update timer labels
        self.window.after(1000, self.update_timers)

    def close(self):
        self.pb.stop()
        self.window.destroy()

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

    def _append(self, box: scrolledtext.ScrolledText, text: str | None = None, tag: str | None = None, extra_space: bool = False):
        box.config(state="normal")
        ts = time.strftime("[%H:%M:%S] ")
        box.insert(tk.END, ts, "timestamp")
        if tag:
            box.insert(tk.END, (text or self.status_var.get()) + "\n", tag)
        else:
            box.insert(tk.END, (text or self.status_var.get()) + "\n")
        if extra_space:
            box.insert(tk.END, "\n")
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
        self._append(self.log_box)
        if msg.startswith("  "):
            self._append(self.detail_log, msg.strip(), extra_space=True)
        elif m:
            lam = self.items[pair_idx].get("lamType", "")
            color = get_laminate_color(lam)
            tag = f"lam_{color}"
            if not self.pair_log.tag_cget(tag, "foreground"):
                self.pair_log.tag_config(tag, foreground=color)
                self.detail_log.tag_config(tag, foreground=color)
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
            self._append(self.detail_log, entry + details + time_note, tag, extra_space=True)
        else:
            self._append(self.detail_log, extra_space=True)
            if "art" in lower:
                self._append(self.art_log)
            if "template" in lower:
                self._append(self.template_log)
