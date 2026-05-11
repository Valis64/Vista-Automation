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
    def test_has_sample_pairs_detects_sample_flag_or_qty(self):
        self.assertTrue(order_gui.has_sample_pairs([{"sample": True, "qty": 1}]))
        self.assertTrue(order_gui.has_sample_pairs([{"sample": False, "qty": 11}]))
        self.assertFalse(order_gui.has_sample_pairs([{"sample": False, "qty": 1}]))
        self.assertTrue(
            order_gui.has_sample_pairs([{"sample": False, "qty": 101}], sample_qty=101)
        )
        self.assertTrue(
            order_gui.has_sample_pairs(
                [{"sample": False, "qty": 101, "sample_quantity": 101}]
            )
        )
        self.assertTrue(
            order_gui.has_sample_pairs([{"sample": False, "qty": 11}], sample_qty=101)
        )
        self.assertTrue(
            order_gui.has_sample_pairs([{"sample": False, "qty": 100}], sample_qty=101)
        )
        self.assertFalse(
            order_gui.has_sample_pairs([{"sample": False, "qty": 10}], sample_qty=101)
        )
        self.assertFalse(
            order_gui.has_sample_pairs([{"sample": False, "qty": 102}], sample_qty=101)
        )

    def test_sample_quantity_normalizes_invalid_values_to_default(self):
        self.assertEqual(order_gui.get_sample_quantity({}), order_gui.DEFAULT_SAMPLE_QUANTITY)
        self.assertEqual(order_gui.get_sample_quantity({"sample_quantity": ""}), 11)
        self.assertEqual(order_gui.get_sample_quantity({"sample_quantity": "0"}), 11)
        self.assertEqual(order_gui.get_sample_quantity({"sample_quantity": "abc"}), 11)
        self.assertEqual(order_gui.get_sample_quantity({"sample_quantity": "101"}), 101)

    def test_save_settings_persists_normalized_sample_quantity(self):
        app = order_gui.App.__new__(order_gui.App)
        app.login_url_var = DummyVar("")
        app.username_var = DummyVar("")
        app.password_var = DummyVar("")
        app.queue_login_url_var = DummyVar("")
        app.queue_username_var = DummyVar("")
        app.queue_password_var = DummyVar("")
        app.queue_page_var = DummyVar("")
        app.ill_path_var = DummyVar("illustrator")
        app.art_dir_var = DummyVar("art")
        app.template_dir_var = DummyVar("templates")
        app.month_dir_var = DummyVar("month")
        app.order_id_var = DummyVar("ORD")
        app.summary_var = DummyVar(False)
        app.art_server_var = DummyVar("")
        app.gdrive_var = DummyVar("")
        app.chat_api_key_var = DummyVar("")
        app.chat_api_url_var = DummyVar(order_gui.CHAT_API_URL)
        app.appearance_var = DummyVar("System")
        app.diagnostic_var = DummyVar(False)
        app.sample_quantity_var = DummyVar("101")
        app.output_lines_var = DummyVar(True)
        app.output_flat_var = DummyVar(True)
        app.review_flats_var = DummyVar(False)
        app.skip_po_no_page2_var = DummyVar(True)
        app.create_blank_po_no_page2_var = DummyVar(False)
        app.preserve_color_var = DummyVar(False)
        app.convert_profile_var = DummyVar(False)

        with mock.patch("order_gui.save_settings") as save_mock:
            app.save_settings()

        saved = save_mock.call_args.args[0]
        self.assertEqual(saved["sample_quantity"], 101)
        self.assertEqual(app.sample_quantity_var.get(), "101")

        app.sample_quantity_var.set("bad")
        with mock.patch("order_gui.save_settings") as save_mock:
            app.save_settings()

        saved = save_mock.call_args.args[0]
        self.assertEqual(saved["sample_quantity"], order_gui.DEFAULT_SAMPLE_QUANTITY)
        self.assertEqual(app.sample_quantity_var.get(), str(order_gui.DEFAULT_SAMPLE_QUANTITY))

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

    def test_get_selected_items_includes_skipped_pairs_with_unchecked_var(self):
        app = order_gui.App.__new__(order_gui.App)
        app.items = [
            {"order_id": "A", "art_dir": "art", "template_dir": "temp", "month_dir": "month"},
            {"order_id": "B", "art_dir": "art", "template_dir": "temp", "month_dir": "month"},
            {"order_id": "C", "art_dir": "art", "template_dir": "temp", "month_dir": "month"},
        ]
        app.batch_items = []
        app.pairs = [
            {
                "art_id": "a1",
                "template": "t1",
                "order_id": "A",
                "skip": True,
                "skip_reason": "Quantity is 1",
            },
            {"art_id": "a2", "template": "t2", "order_id": "B"},
            {"art_id": "a3", "template": "t3", "order_id": "C"},
        ]
        app.batch_pairs = []
        app.pair_vars = [DummyVar(False), DummyVar(False), DummyVar(True)]

        items, pairs, indices = app.get_selected_items()
        self.assertEqual([item["order_id"] for item in items], ["A", "C"])
        self.assertEqual([pair.get("art_id") for pair in pairs], ["a1", "a3"])
        self.assertEqual([pair.get("skip_reason") for pair in pairs], ["Quantity is 1", None])
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
        app.skip_po_no_page2_var = DummyVar(False)
        app.create_blank_po_no_page2_var = DummyVar(True)
        app.preserve_color_var = DummyVar(True)
        app.convert_profile_var = DummyVar(False)
        app.output_lines_var = DummyVar(True)
        app.output_flat_var = DummyVar(True)
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
                return_value=({}, {0}, {0: "No PO art found"}, {1}),
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
        self.assertTrue(saved["pairs"][1].get("blank_template"))
        self.assertEqual(saved["pairs"][1].get("blank_template_reason"), "No page 2 art")
        self.assertEqual([p.get("art_id") for p in saved["pairs"]], ["a1", "a3"])
        self.assertEqual([p.get("template") for p in saved["pairs"]], ["t1", "t3"])
        self.assertFalse(saved.get("skip_po_no_page2"))
        self.assertTrue(saved.get("create_blank_po_no_page2"))

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
        app.skip_po_no_page2_var = DummyVar(True)
        app.create_blank_po_no_page2_var = DummyVar(False)
        app.preserve_color_var = DummyVar(True)
        app.convert_profile_var = DummyVar(False)
        app.output_lines_var = DummyVar(True)
        app.output_flat_var = DummyVar(True)
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
                return_value=({}, set(), {}, set()),
            ), mock.patch(
                "order_gui.save_order_data"
            ) as save_mock:
                app.save_json()

        args, _ = save_mock.call_args
        saved = args[0]
        self.assertEqual(len(saved["pairs"]), 2)
        self.assertTrue(saved["pairs"][0].get("skip"))
        self.assertEqual(saved["pairs"][0].get("skip_reason"), "No Print Box")
        self.assertIsNone(saved["pairs"][0].get("blank_template"))
        self.assertTrue(saved["items"][0].get("skip"))
        self.assertEqual(saved["items"][0].get("skip_reason"), "No Print Box")
        self.assertTrue(saved.get("skip_po_no_page2"))
        self.assertFalse(saved.get("create_blank_po_no_page2"))

    def test_run_illustrator_blocks_sample_launch_when_outputs_disabled(self):
        app = order_gui.App.__new__(order_gui.App)
        app.sample_copy_info = []
        app.items = [
            {
                "order_id": "A",
                "art_dir": "art",
                "template_dir": "temp",
                "month_dir": "month",
                "filename": "sample-job.pdf",
                "gluetab": "left",
            }
        ]
        app.batch_items = []
        app.pairs = [{"art_id": "a1", "template": "t1", "order_id": "A"}]
        app.batch_pairs = []
        app.pair_vars = [DummyVar(True)]
        app.index = 0
        app.fields = {}
        app.art_dir_var = DummyVar("art")
        app.template_dir_var = DummyVar("temp")
        app.month_dir_var = DummyVar("month")
        app.order_id_var = DummyVar("ORD")
        app.summary_var = DummyVar(True)
        app.diagnostic_var = DummyVar(False)
        app.skip_po_no_page2_var = DummyVar(False)
        app.create_blank_po_no_page2_var = DummyVar(True)
        app.preserve_color_var = DummyVar(True)
        app.convert_profile_var = DummyVar(False)
        app.output_lines_var = DummyVar(False)
        app.output_flat_var = DummyVar(False)
        app.run_id = ""
        app.root = mock.Mock()
        app.update_timer = mock.Mock()
        app._apply_paired_page_results = mock.Mock()
        app.save_settings = mock.Mock()
        app.html_content = ""

        with mock.patch("order_gui.messagebox.showerror"), mock.patch(
            "order_gui.messagebox.showwarning"
        ) as warn_mock, mock.patch(
            "order_gui.find_art_file", return_value="art:a1"
        ), mock.patch(
            "order_gui._resolve_template_and_paper", return_value=("template:t1", "paper:t1")
        ), mock.patch(
            "order_gui.get_item_quantity", return_value=11
        ), mock.patch(
            "order_gui.detect_laminate", return_value=""
        ), mock.patch(
            "order_gui.is_coffee_sleeve", return_value=False
        ), mock.patch(
            "order_gui.resolve_paired_page_art",
            return_value=({}, set(), {}, set()),
        ), mock.patch(
            "order_gui.save_order_data"
        ) as save_mock:
            app.run_illustrator()

        warn_mock.assert_called_once()
        self.assertIn("no sample PDFs would be produced", warn_mock.call_args.args[1])
        save_mock.assert_not_called()
        app._apply_paired_page_results.assert_not_called()


if __name__ == "__main__":
    unittest.main()
