"""Tests for the loading window progress logging."""

from __future__ import annotations

import tkinter as tk

import pytest

from loading_window import LoadingWindow
from utils.common import get_laminate_color


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


def test_verbose_log_captures_progress_messages(tk_root):
    items = [
        {
            "company": "Example Co",
            "template": "PB001",
            "lamType": "Gloss",
        }
    ]
    orders = ["ORDER-1"]

    window = LoadingWindow(tk_root, items, orders)
    try:
        window.update_status("Starting job")
        window.update_status("Processing pair 1 of 1")
        window.update_status("Finished pair 1 of 1")

        content = window.verbose_log.get("1.0", tk.END).strip().splitlines()
        assert any("Starting job" in line for line in content)
        assert any("Processing pair 1 of 1" in line for line in content)
        assert any("Finished pair 1 of 1" in line for line in content)

        color = get_laminate_color("Gloss")
        tag_name = f"lam_{color}"
        assert window.verbose_log.tag_cget(tag_name, "foreground") == color

        arrow_index = window.verbose_log.search("→", "1.0", tk.END)
        assert arrow_index
        assert tag_name in window.verbose_log.tag_names(arrow_index)
    finally:
        window.close()
