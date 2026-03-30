from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

import pytest
from tkinter import ttk

from order_gui import (
    App,
    _can_enable_template_save,
    _resolve_template_settings_code,
)


def test_can_enable_template_save_requires_loaded_code_and_valid_unsaved():
    assert not _can_enable_template_save(None, True, True)
    assert not _can_enable_template_save("ZZ1000", False, True)
    assert not _can_enable_template_save("ZZ1000", True, False)
    assert _can_enable_template_save("ZZ1000", True, True)


def test_resolve_template_settings_code_prefers_current_code():
    assert _resolve_template_settings_code("ZZ1000", ()) == "ZZ1000"
    assert _resolve_template_settings_code(None, ("ZZ2000",)) == "ZZ2000"
    assert _resolve_template_settings_code(None, ()) is None


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter GUI is not available in this environment")
    root.withdraw()
    yield root
    root.destroy()


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _find_template_tree(top_level: tk.Toplevel) -> ttk.Treeview:
    for widget in _walk(top_level):
        if isinstance(widget, ttk.Treeview) and "bleedMode" in widget["columns"]:
            return widget
    raise AssertionError("Template settings tree not found")


def _find_template_save_button(top_level: tk.Toplevel) -> tk.Button:
    for widget in _walk(top_level):
        if not isinstance(widget, tk.Button) or widget.cget("text") != "Save":
            continue
        sibling_texts = {
            child.cget("text")
            for child in widget.master.winfo_children()
            if isinstance(child, tk.Button)
        }
        if {"Save", "Add", "Delete"}.issubset(sibling_texts):
            return widget
    raise AssertionError("Template settings save button not found")


def test_template_editor_save_stays_enabled_without_reselect(tk_root, tmp_path: Path):
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Template settings",
        "type": "object",
        "properties": {
            "rotation": {"type": "integer"},
            "bleedPaths": {"type": "array", "items": {"type": "string"}},
            "bleedMode": {"type": "string", "enum": ["auto", "manual"]},
            "mirror": {"type": "boolean"},
            "artworkScale": {"type": "number", "minimum": 0},
            "alignment": {"type": "string"},
        },
        "additionalProperties": False,
    }
    (tmp_path / "schema.json").write_text(json.dumps(schema))
    code = "ZZ9001"
    (tmp_path / f"{code}.json").write_text(
        json.dumps(
            {
                "rotation": 0,
                "bleedPaths": ["bleed_old"],
                "bleedMode": "manual",
                "mirror": False,
                "artworkScale": 1.0,
                "alignment": "center",
            }
        )
    )

    app = App.__new__(App)
    app.root = tk_root

    with (
        patch("order_gui.TEMPLATE_SETTINGS_DIR", tmp_path),
        patch("utils.common.TEMPLATE_SETTINGS_DIR", tmp_path),
        patch("order_gui.load_bleed_failsafe_settings", return_value={}),
    ):
        App.open_template_settings_editor(app, code=code)
        tk_root.update()

        win = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
        tree = _find_template_tree(win)
        save_btn = _find_template_save_button(win)

        assert save_btn.cget("state") == "disabled"

        tree.selection_set(code)
        tree.event_generate("<<TreeviewSelect>>")
        tk_root.update()

        bleed_entry = next(
            widget
            for widget in _walk(win)
            if isinstance(widget, tk.Entry) and widget.get() == "bleed_old"
        )

        tree.selection_remove(code)
        tk_root.update()

        bleed_entry.delete(0, tk.END)
        bleed_entry.insert(0, "bleed_new")
        tk_root.update()

        assert save_btn.cget("state") == "normal"

        save_btn.invoke()
        tk_root.update()
        updated = json.loads((tmp_path / f"{code}.json").read_text())
        assert updated["bleedPaths"] == ["bleed_new"]

        win.destroy()
