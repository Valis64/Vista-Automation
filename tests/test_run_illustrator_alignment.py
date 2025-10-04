"""Regression tests for the Illustrator launch workflow alignment."""

from __future__ import annotations

import tkinter as tk

import pytest

import order_gui


@pytest.fixture
def tk_root():
    """Provide a Tk root window or skip if Tk is unavailable."""

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter GUI is not available in this environment")
    root.withdraw()
    yield root
    root.destroy()


def test_run_illustrator_preserves_pair_alignment(tk_root, monkeypatch):
    """Selecting later checklist rows keeps art/template metadata aligned."""

    app = order_gui.App(tk_root)
    app.items = [
        {"filename": "first.ai", "order_id": "ORDER-1", "qty": 5},
        {"filename": "second.ai", "order_id": "ORDER-2", "qty": 7},
        {"filename": "third.ai", "order_id": "ORDER-3", "qty": 9},
    ]
    app.pairs = [
        {"art_id": "ART-1", "template": "T1", "order_id": "ORDER-1"},
        {"art_id": "ART-2", "template": "T2", "order_id": "ORDER-2"},
        {"art_id": "ART-3", "template": "T3", "order_id": "ORDER-3"},
    ]
    app.batch_items = []
    app.batch_pairs = []

    app.pair_vars = [tk.BooleanVar(master=tk_root, value=False) for _ in app.items]
    app.pair_vars[1].set(True)
    app.pair_vars[2].set(True)

    app.art_dir_var.set("/art")
    app.template_dir_var.set("/templates")
    app.month_dir_var.set("/month")
    app.order_id_var.set("ORDER-DEFAULT")

    monkeypatch.setattr(order_gui, "find_art_file", lambda *args, **kwargs: "art-path")
    monkeypatch.setattr(order_gui, "find_template_file", lambda *args, **kwargs: "template-path")
    monkeypatch.setattr(order_gui, "extract_paper_type", lambda *_: "Paper")
    monkeypatch.setattr(order_gui, "detect_laminate", lambda *_: "")
    monkeypatch.setattr(order_gui, "is_coffee_sleeve", lambda *_: False)
    monkeypatch.setattr(order_gui, "get_item_quantity", lambda item: item.get("qty", 0))
    monkeypatch.setattr(order_gui, "cut_file_for_template", lambda *_: "")
    monkeypatch.setattr(order_gui, "resolve_paired_page_art", lambda *_1, **_2: ({}, set()))
    monkeypatch.setattr(order_gui, "prepare_flat_review_entries", lambda *_1, **_2: ([], []))
    monkeypatch.setattr(order_gui, "write_paper_summary", lambda *_: None)
    monkeypatch.setattr(order_gui, "launch_illustrator", lambda *_: None)
    monkeypatch.setattr(order_gui, "record_run_history", lambda *_: None)
    monkeypatch.setattr(order_gui, "save_order_html", lambda *_: None)

    class DummyLoader:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def update_status(self, *_: object, **__: object) -> None:
            pass

        def close(self) -> None:
            pass

    class DummyThread:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def start(self) -> None:
            pass

    monkeypatch.setattr(order_gui, "LoadingWindow", DummyLoader)
    monkeypatch.setattr(order_gui.threading, "Thread", DummyThread)

    captured: dict[str, dict] = {}

    def fake_save_order_data(payload: dict) -> None:
        captured["payload"] = payload

    monkeypatch.setattr(order_gui, "save_order_data", fake_save_order_data)

    app.run_illustrator()

    assert "payload" in captured
    pairs = captured["payload"]["pairs"]
    assert [p["art_id"] for p in pairs] == ["ART-2", "ART-3"]
    assert [p["template"] for p in pairs] == ["T2", "T3"]
    assert [item["filename"] for item in captured["payload"]["items"]] == [
        "second.ai",
        "third.ai",
    ]
