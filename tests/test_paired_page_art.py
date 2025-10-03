import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
