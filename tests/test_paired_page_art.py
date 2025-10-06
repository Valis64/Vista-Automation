import os
import tempfile
import unittest
import zipfile

import order_gui

from order_gui import (
    find_template_file,
    prepare_flat_review_entries,
    resolve_paired_page_art,
    resolve_print_output_folder,
    sanitize_filename_base,
)


class ResolvePairedPageArtTests(unittest.TestCase):
    def _build_context(self, art_id: str, order_id: str, month_root: str, art_path: str = "") -> dict:
        return {
            "art_id": art_id,
            "order_id": order_id,
            "month_root": month_root,
            "art_root": "",
            "art_path": art_path,
            "template": "",
        }

    def test_maps_pages_for_base_and_mate(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "12345"
            art_id = "ART001"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            page1 = os.path.join(folder, "page1.pdf")
            page2 = os.path.join(folder, "page2.pdf")
            with open(page1, "w", encoding="utf-8"):
                pass
            with open(page2, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO1", "art_path": ""},
                {"template": "PO1B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp),
                self._build_context(art_id, order_id, tmp),
            ]
            logs: list[str] = []

            assignments, skips = resolve_paired_page_art(entries, contexts, logs.append)

            self.assertEqual(assignments.get(0), page1)
            self.assertEqual(assignments.get(1), page2)
            self.assertFalse(skips)
            self.assertTrue(any("Resolved zip folder" in msg for msg in logs))

    def test_missing_page_skips_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "54321"
            art_id = "ART002"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            page1 = os.path.join(folder, "page1.pdf")
            with open(page1, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO2", "art_path": ""},
                {"template": "PO2B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp),
                self._build_context(art_id, order_id, tmp),
            ]
            logs: list[str] = []

            assignments, skips = resolve_paired_page_art(entries, contexts, logs.append)

            self.assertEqual(assignments.get(0), page1)
            self.assertIn(1, skips)
            self.assertTrue(any("page2.pdf not found" in msg for msg in logs))

    def test_missing_mate_logs_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "88888"
            art_id = "ART003"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            page1 = os.path.join(folder, "page1.pdf")
            with open(page1, "w", encoding="utf-8"):
                pass

            entries = [{"template": "PO3", "art_path": ""}]
            contexts = [self._build_context(art_id, order_id, tmp)]
            logs: list[str] = []

            assignments, skips = resolve_paired_page_art(entries, contexts, logs.append)

            self.assertEqual(assignments.get(0), page1)
            self.assertFalse(skips)
            self.assertTrue(any("missing mate template" in msg for msg in logs))

    def test_case_insensitive_page_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "77777"
            art_id = "ART004"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            page1 = os.path.join(folder, "PaGe1.PDF")
            page2 = os.path.join(folder, "PAGE2.PDF")
            with open(page1, "w", encoding="utf-8"):
                pass
            with open(page2, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO4", "art_path": ""},
                {"template": "PO4B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp),
                self._build_context(art_id, order_id, tmp),
            ]
            logs: list[str] = []

            assignments, skips = resolve_paired_page_art(entries, contexts, logs.append)

            self.assertEqual(assignments.get(0), page1)
            self.assertEqual(assignments.get(1), page2)
            self.assertFalse(skips)

    def test_find_template_prefers_exact_template_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            po1_path = os.path.join(tmp, "PO1_print 10in -vp.ai")
            po1b_path = os.path.join(tmp, "PO1B_print 09in -vp.ai")

            with open(po1_path, "w", encoding="utf-8"):
                pass
            with open(po1b_path, "w", encoding="utf-8"):
                pass

            result = find_template_file(tmp, "PO1")

            self.assertEqual(result, po1_path)

    def test_flat_entries_include_assigned_art_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "90001"
            art_id = "ART900"
            template = "P15"
            art_folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(art_folder, exist_ok=True)
            page1 = os.path.join(art_folder, "page1.pdf")
            page2 = os.path.join(art_folder, "page2.pdf")
            for path in (page1, page2):
                with open(path, "w", encoding="utf-8"):
                    pass

            entries = [{"template": template, "art_path": ""}]
            contexts = [
                {
                    "art_id": art_id,
                    "order_id": order_id,
                    "month_root": tmp,
                    "art_root": "",
                    "art_path": "",
                    "template": template,
                }
            ]
            logs: list[str] = []

            assignments, skips = resolve_paired_page_art(entries, contexts, logs.append)

            self.assertIn(0, assignments)
            self.assertFalse(skips)

            filename_base = sanitize_filename_base("Sample File")
            candidates = [
                {
                    "idx": 0,
                    "filename_base": filename_base,
                    "template": template,
                    "paper": "SBS",
                    "order_id": order_id,
                    "art_id": art_id,
                    "glue": "",
                    "lam": "",
                    "art_path": "",
                    "template_path": "",
                    "sample": False,
                    "cut_src": "",
                }
            ]

            flat_entries, sample_entries = prepare_flat_review_entries(
                candidates,
                assignments,
                skips,
                diagnostic=False,
            )

            self.assertFalse(sample_entries)
            self.assertEqual(len(flat_entries), 1)
            _, flat_path, info = flat_entries[0]

            expected_folder = resolve_print_output_folder(
                assignments[0],
                template,
                "",
                diagnostic=False,
            )
            expected_flat = os.path.join(
                expected_folder,
                f"{filename_base}_flat_SBS.pdf",
            )

            self.assertEqual(flat_path, expected_flat)
            self.assertEqual(info[0], expected_flat)
            self.assertEqual(info[-1], assignments[0])

    def test_pb_templates_are_ignored_by_pairing(self):
        with tempfile.TemporaryDirectory() as tmp:
            art_pdf = os.path.join(tmp, "art.pdf")
            with open(art_pdf, "w", encoding="utf-8"):
                pass

            entries = [{"template": "PB001", "art_path": art_pdf}]
            contexts = [
                {
                    "art_id": "PBART",
                    "order_id": "10001",
                    "month_root": tmp,
                    "art_root": "",
                    "art_path": art_pdf,
                    "template": "PB001",
                }
            ]
            logs: list[str] = []

            assignments, skips = resolve_paired_page_art(entries, contexts, logs.append)

            self.assertFalse(assignments)
            self.assertFalse(skips)

    def test_flat_entries_resolve_existing_flat_filename_for_p_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "36349"
            art_id = "M38EA03C07"
            template = "PO1"
            art_dir = os.path.join(tmp, order_id, "art")
            os.makedirs(art_dir, exist_ok=True)
            art_path = os.path.join(art_dir, f"{art_id}.pdf")
            with open(art_path, "w", encoding="utf-8"):
                pass

            print_dir = os.path.join(tmp, "print")
            os.makedirs(print_dir, exist_ok=True)
            actual_name = (
                "36349 - McKenzie Crest Inc. - Justin - "
                "PO1_M38EA03C07 - PO1_#1_print_flat_SBS.pdf"
            )
            with open(os.path.join(print_dir, actual_name), "w", encoding="utf-8"):
                pass

            candidates = [
                {
                    "idx": 0,
                    "filename_base": "36349 - McKenzie Crest Inc",
                    "template": template,
                    "paper": "SBS",
                    "order_id": order_id,
                    "art_id": art_id,
                    "glue": "36349 - McKenzie Crest Inc. - Justin - #1",
                    "lam": "Gloss",
                    "art_path": art_path,
                    "template_path": "",
                    "sample": False,
                    "cut_src": "",
                    "company": "McKenzie Crest Inc.",
                    "created_by": "Justin",
                }
            ]

            flat_entries, sample_entries = prepare_flat_review_entries(
                candidates,
                {},
                [],
                diagnostic=False,
            )

            self.assertFalse(sample_entries)
            self.assertEqual(len(flat_entries), 1)
            _, flat_path, info = flat_entries[0]
            expected_path = os.path.join(print_dir, actual_name)

            self.assertEqual(flat_path, expected_path)
            self.assertEqual(info[0], expected_path)


class MoveArtToArtFoldersTests(unittest.TestCase):
    class _Var:
        def __init__(self, value: str = "") -> None:
            self.value = value

        def get(self) -> str:
            return self.value

        def set(self, value: str) -> None:
            self.value = value

    def test_warns_when_page2_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            month_dir = os.path.join(tmp, "2024-01")
            order_id = "1001"
            order_dir = os.path.join(month_dir, order_id)
            os.makedirs(order_dir, exist_ok=True)
            zip_path = os.path.join(order_dir, "PO1.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("page1.pdf", "data")

            app = order_gui.App.__new__(order_gui.App)
            app.items = [
                {
                    "order_id": order_id,
                    "month_dir": month_dir,
                    "template_dir": "",
                    "art_dir": "",
                },
                {
                    "order_id": order_id,
                    "month_dir": month_dir,
                    "template_dir": "",
                    "art_dir": "",
                },
            ]
            app.batch_items = []
            app.pairs = [
                {"art_id": "PO1", "template": "PO1"},
                {"art_id": "PO1", "template": "PO1B"},
            ]
            app.batch_pairs = []
            app.month_dir_var = self._Var(month_dir)
            app.art_dir_var = self._Var("")
            app.template_dir_var = self._Var("")
            app.order_id_var = self._Var(order_id)

            summary: dict[str, list[str]] = {}

            def fake_summary(art_files: int, zip_count: int, *, extra_warnings=None):
                summary["warnings"] = list(extra_warnings or [])

            app._show_art_move_summary = fake_summary  # type: ignore[method-assign]

            logs: list[str] = []
            app.log_message = logs.append  # type: ignore[method-assign]

            app.move_art_to_art_folders()

            self.assertTrue(any("page2.pdf not found" in msg for msg in logs))
            self.assertIn("warnings", summary)
            self.assertTrue(any("page2.pdf not found" in msg for msg in summary["warnings"]))


if __name__ == "__main__":
    unittest.main()
