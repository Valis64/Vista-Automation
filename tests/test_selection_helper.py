import unittest
from unittest import mock

import order_gui


class DummyVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class SelectionHelperTest(unittest.TestCase):
    def test_get_selected_items_returns_pairs_and_indices(self):
        app = order_gui.App.__new__(order_gui.App)
        app.items = [
            {"order_id": "A", "art_dir": "art", "template_dir": "temp", "month_dir": "month"},
            {"order_id": "B", "art_dir": "art", "template_dir": "temp", "month_dir": "month"},
            {"order_id": "C", "art_dir": "art", "template_dir": "temp", "month_dir": "month"},
        ]
        app.batch_items = []
        app.pairs = [
            {"art_id": "a1", "template": "t1", "order_id": "A"},
            {"art_id": "a2", "template": "t2", "order_id": "B"},
            {"art_id": "a3", "template": "t3", "order_id": "C"},
        ]
        app.batch_pairs = []
        app.pair_vars = [DummyVar(True), DummyVar(False), DummyVar(True)]

        items, pairs, indices = app.get_selected_items()
        self.assertEqual([item["order_id"] for item in items], ["A", "C"])
        self.assertEqual([pair.get("art_id") for pair in pairs], ["a1", "a3"])
        self.assertEqual(indices, [0, 2])

    def test_save_json_uses_filtered_pairs(self):
        app = order_gui.App.__new__(order_gui.App)
        app.batch_items = []
        app.batch_pairs = []
        app.items = [
            {"order_id": "A", "art_dir": "art", "template_dir": "temp", "month_dir": "month"},
            {"order_id": "B", "art_dir": "art", "template_dir": "temp", "month_dir": "month"},
            {"order_id": "C", "art_dir": "art", "template_dir": "temp", "month_dir": "month"},
        ]
        app.pairs = [
            {"art_id": "a1", "template": "t1", "order_id": "A"},
            {"art_id": "a2", "template": "t2", "order_id": "B"},
            {"art_id": "a3", "template": "t3", "order_id": "C"},
        ]
        app.pair_vars = [DummyVar(True), DummyVar(False), DummyVar(True)]
        app.index = 0
        app.fields = {}
        app.art_dir_var = DummyVar("art")
        app.template_dir_var = DummyVar("temp")
        app.month_dir_var = DummyVar("month")
        app.order_id_var = DummyVar("ORD")
        app.summary_var = DummyVar(True)
        app.diagnostic_var = DummyVar(False)
        app.preserve_color_var = DummyVar(True)
        app.convert_profile_var = DummyVar(False)
        app.run_id = ""
        app.order_info_vars = {
            "order_id": DummyVar("ORD"),
            "company": DummyVar("Comp"),
            "sales_rep": DummyVar("Rep"),
        }
        app.save_settings = lambda: None

        with mock.patch("order_gui.messagebox.showerror"), mock.patch(
            "order_gui.messagebox.showinfo"
        ), mock.patch("order_gui.find_art_file", side_effect=lambda *a, **k: f"art:{a[1]}"):
            with mock.patch(
                "order_gui._resolve_template_and_paper",
                side_effect=lambda *a, **k: (f"template:{a[1]}", f"paper:{a[1]}"),
            ), mock.patch("order_gui.detect_laminate", return_value=""), mock.patch(
                "order_gui.is_coffee_sleeve", return_value=False
            ), mock.patch(
                "order_gui.resolve_paired_page_art",
                return_value=({}, {0}, {0: "No PO art found"}),
            ), mock.patch(
                "order_gui.save_order_data"
            ) as save_mock:
                app.save_json()

        args, _ = save_mock.call_args
        saved = args[0]
        self.assertEqual(len(saved["items"]), 2)
        self.assertEqual(saved["items"][0].get("skip_reason"), "No PO art found")
        self.assertTrue(saved["pairs"][0].get("skip"))
        self.assertEqual(saved["pairs"][0].get("skip_reason"), "No PO art found")
        self.assertEqual([p.get("art_id") for p in saved["pairs"]], ["a1", "a3"])
        self.assertEqual([p.get("template") for p in saved["pairs"]], ["t1", "t3"])

    def test_save_json_preserves_existing_skip_flags(self):
        app = order_gui.App.__new__(order_gui.App)
        app.batch_items = []
        app.batch_pairs = []
        app.items = [
            {"order_id": "A", "art_dir": "art", "template_dir": "temp", "month_dir": "month"},
            {"order_id": "B", "art_dir": "art", "template_dir": "temp", "month_dir": "month"},
        ]
        app.pairs = [
            {
                "art_id": "",
                "template": "PO123B",
                "order_id": "A",
                "skip": True,
                "skip_reason": "No Print Box",
            },
            {"art_id": "a2", "template": "t2", "order_id": "B"},
        ]
        app.pair_vars = [DummyVar(True), DummyVar(True)]
        app.index = 0
        app.fields = {}
        app.art_dir_var = DummyVar("art")
        app.template_dir_var = DummyVar("temp")
        app.month_dir_var = DummyVar("month")
        app.order_id_var = DummyVar("ORD")
        app.summary_var = DummyVar(True)
        app.diagnostic_var = DummyVar(False)
        app.preserve_color_var = DummyVar(True)
        app.convert_profile_var = DummyVar(False)
        app.run_id = ""
        app.order_info_vars = {
            "order_id": DummyVar("ORD"),
            "company": DummyVar("Comp"),
            "sales_rep": DummyVar("Rep"),
        }
        app.save_settings = lambda: None

        with mock.patch("order_gui.messagebox.showerror"), mock.patch(
            "order_gui.messagebox.showinfo"
        ), mock.patch(
            "order_gui.find_art_file", side_effect=lambda *a, **k: f"art:{a[1]}"
        ):
            with mock.patch(
                "order_gui._resolve_template_and_paper",
                side_effect=lambda *a, **k: (f"template:{a[1]}", f"paper:{a[1]}"),
            ), mock.patch("order_gui.detect_laminate", return_value=""), mock.patch(
                "order_gui.is_coffee_sleeve", return_value=False
            ), mock.patch(
                "order_gui.resolve_paired_page_art",
                return_value=({}, set(), {}),
            ), mock.patch(
                "order_gui.save_order_data"
            ) as save_mock:
                app.save_json()

        args, _ = save_mock.call_args
        saved = args[0]
        self.assertEqual(len(saved["pairs"]), 2)
        self.assertTrue(saved["pairs"][0].get("skip"))
        self.assertEqual(saved["pairs"][0].get("skip_reason"), "No Print Box")
        self.assertTrue(saved["items"][0].get("skip"))
        self.assertEqual(saved["items"][0].get("skip_reason"), "No Print Box")


if __name__ == "__main__":
    unittest.main()
