# review.py
"""Utilities for reviewing generated PDFs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
import tkinter as tk
import tkinter.font as tkfont
from tkinter import simpledialog

# Determine application directory similar to order_gui
if getattr(sys, "frozen", False):
    APP_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    APP_DIR = Path(__file__).resolve().parent

FLAGS_FILE = APP_DIR / "flags.json"

# Reasons displayed when flagging a PDF during review
FLAG_REASONS = [
    "Convert to grayscale",
    "Bleed",
    "Alignment",
    "Artifacts",
    "Dieline on Art",
    "Color Adjustments",
]


class FlagStatus(Enum):
    """Possible review states for a flagged file."""

    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"


@dataclass
class FlaggedItem:
    """Representation of a flagged file awaiting review."""

    id: str
    path: str
    reasons: list[str]
    status: FlagStatus = FlagStatus.OPEN
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if isinstance(self.status, str):
            try:
                self.status = FlagStatus(self.status)
            except ValueError:
                self.status = FlagStatus.OPEN
        if isinstance(self.reasons, str):
            self.reasons = [self.reasons]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "reasons": self.reasons,
            "status": self.status.value,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def load_flags(path: str | os.PathLike = FLAGS_FILE) -> list[FlaggedItem]:
    """Return unresolved flagged items from ``path``."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        items = []
        for d in data:
            if "reasons" not in d and "reason" in d:
                d["reasons"] = [d.pop("reason")]
            items.append(FlaggedItem(**d))
        return items
    except Exception:
        return []


def save_flags(items: list[FlaggedItem], path: str | os.PathLike = FLAGS_FILE) -> None:
    """Persist ``items`` to ``path`` as JSON."""
    p = Path(path)
    try:
        with p.open("w", encoding="utf-8") as f:
            json.dump([i.to_dict() for i in items], f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Review management
# ---------------------------------------------------------------------------

class ReviewManager:
    """Manage flagged items and review operations."""

    def __init__(self, app: Any, tree: tk.Widget, menu: tk.Menu):
        self.app = app
        self.task_tree = tree
        self.review_menu = menu
        self.flagged_items: list[FlaggedItem] = load_flags()
        self.tree_items: dict[str, FlaggedItem] = {}
        for item in self.flagged_items:
            self._add_flagged_item(item)

        self.task_tree.bind("<Double-Button-1>", self.on_review_double)
        self.task_tree.bind("<Triple-Button-1>", self.on_review_triple)
        self.task_tree.bind("<Button-3>", self.show_review_menu)

    # Tree helpers ---------------------------------------------------------
    def _add_flagged_item(self, item: FlaggedItem) -> None:
        values = (
            os.path.basename(item.path),
            ", ".join(item.reasons),
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.timestamp)),
            item.status.value,
        )
        iid = self.task_tree.insert("", "end", values=values, tags=(item.status.value,))
        self.tree_items[iid] = item
        if item.status is FlagStatus.OPEN:
            self.task_tree.item(iid, tags=("open",))

    def on_review_double(self, event) -> None:
        iid = self.task_tree.identify_row(event.y)
        if not iid:
            sel = self.task_tree.selection()
            if not sel:
                return
            iid = sel[0]
        item = self.tree_items.get(iid)
        if item:
            self.app.open_in_illustrator(item.path)

    def on_review_triple(self, event) -> None:
        iid = self.task_tree.identify_row(event.y)
        if not iid:
            sel = self.task_tree.selection()
            if not sel:
                return
            iid = sel[0]
        item = self.tree_items.get(iid)
        if item:
            self.app.open_in_acrobat(item.path)

    def resolve_selected_tasks(self) -> None:
        self._set_selected_status(FlagStatus.RESOLVED)

    def ignore_selected_tasks(self) -> None:
        self._set_selected_status(FlagStatus.IGNORED)

    def open_selected_items(self) -> None:
        for iid in self.task_tree.selection():
            item = self.tree_items.get(iid)
            if item:
                self.app.open_in_acrobat(item.path)

    def remove_resolved_tasks(self) -> None:
        removed = False
        for iid in list(self.tree_items.keys()):
            item = self.tree_items[iid]
            if item.status is FlagStatus.RESOLVED:
                self.task_tree.delete(iid)
                self.flagged_items.remove(item)
                del self.tree_items[iid]
                removed = True
        if removed:
            from utils.history import update_last_run_flagged
            update_last_run_flagged(self.flagged_items)

    def show_review_menu(self, event) -> None:
        iid = self.task_tree.identify_row(event.y)
        if iid:
            self.task_tree.selection_set(iid)
        self.review_menu.tk_popup(event.x_root, event.y_root)

    def _set_selected_status(self, status: FlagStatus) -> None:
        changed = False
        for iid in self.task_tree.selection():
            item = self.tree_items.get(iid)
            if item and item.status != status:
                item.status = status
                self.task_tree.set(iid, "status", status.value)
                if status is FlagStatus.OPEN:
                    self.task_tree.item(iid, tags=("open",))
                else:
                    self.task_tree.item(iid, tags=(status.value,))
                changed = True
        if changed:
            from utils.history import update_last_run_flagged
            update_last_run_flagged(self.flagged_items)

    # Flat review completion ----------------------------------------------
    def flat_review_complete(self, flagged: list[FlaggedItem]) -> None:
        self.flagged_items.extend(flagged)
        for item in flagged:
            self._add_flagged_item(item)
        if self.task_tree.get_children():
            self.task_tree.see(self.task_tree.get_children()[-1])
        from utils.history import update_last_run_flagged
        update_last_run_flagged(self.flagged_items)

    # Flat review dialog ---------------------------------------------------
    def start_flat_review(self, info_list: list[dict]) -> None:
        if not info_list:
            return

        manager = self

        class Reviewer:
            def __init__(self, info_list: list[dict]):
                self.info_list = info_list
                self.index = 0
                self.flagged: list[FlaggedItem] = []
                self._build_window()
                self._load_current()

            def _build_window(self) -> None:
                self.win = tk.Toplevel(manager.app.root)
                self.win.title("Flat Review")
                self.win.attributes("-topmost", True)
                try:
                    big = tkfont.nametofont("TkDefaultFont").copy()
                    big.configure(size=big.cget("size") + 3)
                    self.win.option_add("*Font", big)
                except Exception:
                    pass

                frame = tk.Frame(self.win)
                frame.pack(fill="both", expand=True)
                frame.grid_columnconfigure(0, weight=0)
                frame.grid_columnconfigure(1, weight=1)
                frame.grid_rowconfigure(0, weight=1)

                self.status_bar = tk.Frame(frame, bg="black")
                self.status_bar.grid(row=0, column=0, rowspan=3, sticky="ns")

                display = tk.Frame(frame)
                display.grid(row=0, column=1, sticky="nsew")
                display.grid_columnconfigure(0, weight=1)
                display.grid_columnconfigure(1, weight=1)
                display.grid_rowconfigure(0, weight=1)

                self.pdf_label = tk.Label(display)
                self.pdf_label.grid(row=0, column=0, sticky="nsew")

                self.art_holder = tk.Frame(display, bd=2, relief="groove")
                self.art_holder.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
                self.art_holder.grid_rowconfigure(0, weight=1)

                info_frame = tk.Frame(frame, bg="black")
                info_frame.grid(row=1, column=1, sticky="ew", pady=4)
                info_frame.grid_columnconfigure(0, weight=1)
                self.order_var = tk.StringVar()
                self.pair_var = tk.StringVar()
                info_inner = tk.Frame(info_frame, bg="black")
                info_inner.grid(row=0, column=0)
                info_font = tkfont.Font(weight="bold")
                for txt, var in (("Order ", self.order_var), (" - Pair ", self.pair_var)):
                    tk.Label(info_inner, text=txt, bg="black", fg="dark green", font=info_font).pack(side="left")
                    tk.Label(info_inner, textvariable=var, bg="black", fg="yellow", font=info_font).pack(side="left")

                self.btn_frame = tk.Frame(frame)
                self.btn_frame.grid(row=2, column=1, pady=5)

                nav = tk.Frame(frame)
                nav.grid(row=3, column=1, pady=5)
                self.prev_btn = tk.Button(nav, text="Previous", command=self.prev_item)
                self.prev_btn.pack(side="left", padx=10)
                self.index_var = tk.StringVar()
                tk.Label(nav, textvariable=self.index_var).pack(side="left")
                self.next_btn = tk.Button(nav, text="Next", command=self.next_item)
                self.next_btn.pack(side="left", padx=10)

            def prev_item(self) -> None:
                if self.index > 0:
                    self.index -= 1
                    self._load_current()

            def next_item(self) -> None:
                if self.index < len(self.info_list) - 1:
                    self.index += 1
                    self._load_current()
                else:
                    self.finish()

            def finish(self) -> None:
                self.win.destroy()
                manager.flat_review_complete(self.flagged)

            def _load_current(self) -> None:
                item = self.info_list[self.index] or {}
                path = item.get("flat_path", "")
                order_id = item.get("order_id", "")
                pair_num = item.get("pair_number", "")
                art_id = item.get("art_id", "")
                glue = item.get("gluetab", "")
                templ = item.get("template", "")
                lam = item.get("laminate", "")
                art_entries_raw = item.get("art_paths") or []
                normalized_entries: list[dict[str, str]] = []
                for entry in art_entries_raw:
                    if isinstance(entry, dict):
                        label = entry.get("label", "")
                        art_path = entry.get("path", "")
                    elif isinstance(entry, (list, tuple)):
                        label = entry[0] if entry else ""
                        art_path = entry[1] if len(entry) > 1 else ""
                    else:
                        label = ""
                        art_path = entry
                    if art_path:
                        normalized_entries.append({"label": label, "path": art_path})
                fallback_path = item.get("art_path")
                if fallback_path and all(fallback_path != e.get("path") for e in normalized_entries):
                    normalized_entries.append({"label": "", "path": fallback_path})

                for w in self.status_bar.winfo_children():
                    w.destroy()
                status_font = tkfont.Font(weight="bold")
                for row, (lbl, val) in enumerate(
                    (
                        ("Art ID:", art_id),
                        ("Gluetab:", glue),
                        ("Template:", templ),
                        ("Laminate:", lam),
                    )
                ):
                    tk.Label(self.status_bar, text=lbl, bg="black", fg="dark green", font=status_font).grid(
                        row=row, column=0, sticky="w", padx=4, pady=1
                    )
                    tk.Label(self.status_bar, text=val, bg="black", fg="yellow", font=status_font).grid(
                        row=row, column=1, sticky="w", padx=(0, 10), pady=1
                    )
                self.status_bar.update_idletasks()

                self.order_var.set(order_id)
                self.pair_var.set(str(pair_num))
                self.index_var.set(f"{self.index + 1} / {len(self.info_list)}")

                for w in self.art_holder.winfo_children():
                    w.destroy()

                try:
                    import fitz
                    from PIL import Image, ImageTk

                    doc = fitz.open(path)
                    page = doc.load_page(0)
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.12, 1.12))
                    mode = "RGBA" if pix.alpha else "RGB"
                    img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                    photo = ImageTk.PhotoImage(img)
                    self.pdf_label.configure(image=photo)
                    self.pdf_label.image = photo
                    self.pdf_label.bind("<Double-Button-1>", lambda e, p=path: manager.app.open_in_illustrator(p))
                    img_w, img_h = pix.width, pix.height
                except Exception:
                    self.pdf_label.configure(text=path)
                    self.pdf_label.image = None
                    img_w, img_h = 800, 600

                max_art_w = max_art_h = 0
                if not normalized_entries:
                    placeholder = tk.Label(self.art_holder, text="No artwork files found")
                    placeholder.grid(row=0, column=0, sticky="nsew")
                    self.art_holder.grid_rowconfigure(0, weight=1)
                else:
                    for idx, entry in enumerate(normalized_entries):
                        art_path = entry.get("path", "")
                        label_text = entry.get("label", "")
                        slot = tk.Frame(self.art_holder, bd=2, relief="groove")
                        slot.grid(row=idx, column=0, sticky="nsew", pady=4)
                        self.art_holder.grid_rowconfigure(idx, weight=1)
                        slot.grid_columnconfigure(0, weight=1)
                        if label_text:
                            tk.Label(slot, text=label_text.title(), font=tkfont.Font(weight="bold")).grid(
                                row=0, column=0, sticky="w", padx=4, pady=2
                            )
                        preview_frame = tk.Frame(slot)
                        preview_frame.grid(row=1, column=0, sticky="nsew")
                        preview_frame.grid_columnconfigure(0, weight=1)
                        preview_frame.grid_rowconfigure(0, weight=1)
                        opener = manager.app.open_in_illustrator
                        if art_path.lower().endswith(".pdf"):
                            opener = manager.app.open_in_acrobat
                        if art_path and os.path.isfile(art_path):
                            try:
                                import fitz
                                from PIL import Image, ImageTk

                                doc = fitz.open(art_path)
                                page = doc.load_page(0)
                                art_pix = page.get_pixmap(matrix=fitz.Matrix(1.12, 1.12))
                                mode = "RGBA" if art_pix.alpha else "RGB"
                                art_img = Image.frombytes(mode, [art_pix.width, art_pix.height], art_pix.samples)
                                art_photo = ImageTk.PhotoImage(art_img)
                                art_label = tk.Label(preview_frame, image=art_photo)
                                art_label.image = art_photo
                                art_label.grid(row=0, column=0, sticky="nsew")
                                art_label.bind(
                                    "<Double-Button-1>",
                                    lambda e, p=art_path, open_cb=opener: open_cb(p),
                                )
                                max_art_w = max(max_art_w, art_pix.width)
                                max_art_h = max(max_art_h, art_pix.height)
                                continue
                            except Exception:
                                pass
                        display_name = os.path.basename(art_path) if art_path else "Unavailable"
                        art_label = tk.Label(preview_frame, text=display_name)
                        art_label.grid(row=0, column=0, sticky="nsew")
                        if art_path:
                            art_label.bind(
                                "<Double-Button-1>",
                                lambda e, p=art_path, open_cb=opener: open_cb(p),
                            )
                        max_art_w = max(max_art_w, 800)
                        max_art_h = max(max_art_h, 600)

                self._build_buttons(path, art_id, normalized_entries)

                total_w = img_w + max_art_w + self.status_bar.winfo_reqwidth()
                total_h = max(img_h, max_art_h)
                sw = self.win.winfo_screenwidth() - 40
                sh = self.win.winfo_screenheight() - 80
                denom_w = total_w if total_w else 1
                denom_h = total_h + 140 if total_h else 1
                scale = min(sw / denom_w, sh / denom_h, 1)
                if scale < 1:
                    try:
                        from PIL import Image, ImageTk

                        if self.pdf_label.image:
                            _ = self.pdf_label.image._PhotoImage__photo.zoom(1)
                    except Exception:
                        pass

            def _build_buttons(self, path: str, art_id: str, art_entries: list[dict[str, str]]) -> None:
                for w in self.btn_frame.winfo_children():
                    w.destroy()

                art_paths = [entry.get("path", "") for entry in art_entries if entry.get("path")]
                first_path = art_paths[0] if art_paths else ""

                def open_art_dir() -> None:
                    if first_path:
                        manager.app.open_directory(os.path.dirname(first_path))

                def approve() -> None:
                    self.next_item()

                def flag() -> None:
                    for widget in self.btn_frame.winfo_children():
                        widget.destroy()
                    reasons = FLAG_REASONS + ["Other..."]
                    vars: list[tk.BooleanVar] = []
                    rb_font = tkfont.Font(weight="bold")
                    for row, text in enumerate(reasons):
                        var = tk.BooleanVar()
                        vars.append(var)
                        tk.Checkbutton(
                            self.btn_frame,
                            text=text,
                            variable=var,
                            font=rb_font,
                            padx=10,
                            pady=5,
                        ).grid(row=row + 1, column=0, columnspan=2, sticky="w", pady=2)

                    def done() -> None:
                        selected: list[str] = []
                        for var, text in zip(vars, reasons):
                            if var.get():
                                if text == "Other...":
                                    other = simpledialog.askstring("Other Reason", "Please describe:", parent=self.win)
                                    if other:
                                        selected.append(other)
                                else:
                                    selected.append(text)
                        if selected:
                            self.flagged.append(FlaggedItem(id=art_id, path=path, reasons=selected))
                        approve()

                    tk.Button(
                        self.btn_frame,
                        text="Flag",
                        width=10,
                        bg="#8B0000",
                        fg="yellow",
                        command=done,
                    ).grid(row=len(reasons) + 1, column=0, pady=5)

                    tk.Button(
                        self.btn_frame,
                        text="Go Back",
                        width=10,
                        command=lambda: self._build_buttons(path, art_id, art_entries),
                    ).grid(row=len(reasons) + 1, column=1, pady=5)

                tk.Button(
                    self.btn_frame,
                    text="Approve",
                    width=10,
                    bg="#4CAF50",
                    fg="white",
                    command=approve,
                ).grid(row=0, column=0, padx=5, pady=3)

                tk.Button(
                    self.btn_frame,
                    text="Flag",
                    width=10,
                    bg="#DC143C",
                    fg="white",
                    command=flag,
                ).grid(row=0, column=1, padx=5, pady=3)

                view_column = 0
                if art_entries:
                    for entry in art_entries:
                        art_path = entry.get("path", "")
                        if not art_path:
                            continue
                        label_text = entry.get("label", "")
                        button_text = "View Art"
                        if label_text:
                            button_text = f"View {label_text.title()}"
                        opener = manager.app.open_in_illustrator
                        if art_path.lower().endswith(".pdf"):
                            opener = manager.app.open_in_acrobat
                        tk.Button(
                            self.btn_frame,
                            text=button_text,
                            width=12,
                            bg="#4682B4",
                            fg="white",
                            command=lambda p=art_path, open_cb=opener: open_cb(p),
                        ).grid(row=1, column=view_column, padx=5, pady=3)
                        view_column += 1
                else:
                    tk.Button(
                        self.btn_frame,
                        text="View Art",
                        width=12,
                        state="disabled",
                    ).grid(row=1, column=view_column, padx=5, pady=3)
                    view_column += 1

                tk.Button(
                    self.btn_frame,
                    text="Art Folder",
                    width=10,
                    command=open_art_dir,
                ).grid(row=1, column=view_column, padx=5, pady=3)

        Reviewer(info_list)

