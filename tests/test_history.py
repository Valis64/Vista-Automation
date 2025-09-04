import unittest
import tempfile
import os
from review import FlaggedItem, FlagStatus, load_flags, save_flags
from utils.history import (
    record_run_history,
    load_run_history,
    update_last_run_flagged,
    summarize_history,
)

import order_gui
from unittest.mock import patch, MagicMock


class RunHistoryTest(unittest.TestCase):
    def test_record_and_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "hist.json")
            record_run_history(5.0, path=path)
            hist = load_run_history(path=path)
            self.assertEqual(len(hist), 1)
            self.assertAlmostEqual(hist[0]["duration"], 5.0, places=1)
            update_last_run_flagged([FlaggedItem(id="1", path="a.pdf", reasons=["test"])], path=path)
            hist = load_run_history(path=path)
            self.assertEqual(len(hist[0]["flagged"]), 1)
            summary = summarize_history(path=path)
            self.assertIn("Runs: 1", summary)

    def test_save_load_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "flags.json")
            items = [
                FlaggedItem(id="1", path="a.pdf", reasons=["x"]),
                FlaggedItem(id="2", path="b.pdf", reasons=["y"]),
            ]
            save_flags(items, path=path)
            loaded = load_flags(path=path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0].path, "a.pdf")

    def test_flagged_item_serialization(self):
        items = [
            FlaggedItem(id="1", path="a.pdf", reasons=["x"], status=FlagStatus.OPEN),
            FlaggedItem(id="2", path="b.pdf", reasons=["y"], status=FlagStatus.RESOLVED),
            FlaggedItem(id="3", path="c.pdf", reasons=["z"], status=FlagStatus.IGNORED),
        ]
        data = [i.to_dict() for i in items]
        loaded = [FlaggedItem(**d) for d in data]
        self.assertEqual([i.status for i in loaded], [FlagStatus.OPEN, FlagStatus.RESOLVED, FlagStatus.IGNORED])

    def test_roundtrip_save_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "flags.json")
            items = [
                FlaggedItem(id="1", path="a.pdf", reasons=["x"], status=FlagStatus.OPEN),
                FlaggedItem(id="2", path="b.pdf", reasons=["y"], status=FlagStatus.RESOLVED),
                FlaggedItem(id="3", path="c.pdf", reasons=["z"], status=FlagStatus.IGNORED),
            ]
            save_flags(items, path=path)
            loaded = load_flags(path=path)
            self.assertEqual([i.to_dict() for i in loaded], [i.to_dict() for i in items])

    def test_app_initializes_with_flags(self):
        flagged = [
            FlaggedItem(id="1", path="a.pdf", reasons=["x"], status=FlagStatus.OPEN),
            FlaggedItem(id="2", path="b.pdf", reasons=["y"], status=FlagStatus.RESOLVED),
        ]

        class DummyRoot:
            def title(self, *a, **k):
                pass

            def winfo_screenwidth(self):
                return 800

            def winfo_screenheight(self):
                return 600

            def geometry(self, *a, **k):
                pass

            def config(self, *a, **k):
                pass

            def quit(self):
                pass

            def after(self, *a, **k):
                pass

            def winfo_rootx(self):
                return 0

            def winfo_rooty(self):
                return 0

        with patch("review.load_flags", return_value=flagged), patch(
            "order_gui.tk", MagicMock()
        ), patch("order_gui.ttk", MagicMock()), patch(
            "order_gui.scrolledtext", MagicMock()
        ), patch(
            "order_gui.tkfont", MagicMock()
        ), patch("order_gui.messagebox", MagicMock()), patch(
            "order_gui.simpledialog", MagicMock()
        ):
            app = order_gui.App(DummyRoot())
            self.assertEqual(app.review.flagged_items, flagged)


if __name__ == "__main__":
    unittest.main()
