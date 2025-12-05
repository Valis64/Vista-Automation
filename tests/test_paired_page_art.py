import os
import tempfile
import unittest
from unittest.mock import patch

import fitz

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

            assignments, skips, skip_reasons = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), page1)
            self.assertEqual(assignments.get(1), page2)
            self.assertFalse(skips)
            self.assertFalse(skip_reasons)
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

            assignments, skips, skip_reasons = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), page1)
            self.assertIn(1, skips)
            self.assertEqual(skip_reasons.get(1), "Missing page2.pdf")
            self.assertTrue(any("page2.pdf not found" in msg for msg in logs))

    def test_two_page_pdf_without_named_pages_is_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "22222"
            art_id = "ARTTWO"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            pdf_path = os.path.join(folder, "art.pdf")

            doc = fitz.open()
            doc.new_page()
            doc.new_page()
            doc.save(pdf_path)
            doc.close()

            entries = [
                {"template": "PO10", "art_path": ""},
                {"template": "PO10B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp),
                self._build_context(art_id, order_id, tmp),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertTrue(assignments.get(0, "").lower().endswith("page1.pdf"))
            self.assertTrue(assignments.get(1, "").lower().endswith("page2.pdf"))
            self.assertTrue(os.path.exists(assignments[0]))
            self.assertTrue(os.path.exists(assignments[1]))
            self.assertFalse(skips)
            self.assertFalse(skip_reasons)

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

            assignments, skips, skip_reasons = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), page1)
            self.assertFalse(skips)
            self.assertFalse(skip_reasons)
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

            assignments, skips, skip_reasons = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), page1)
            self.assertEqual(assignments.get(1), page2)
            self.assertFalse(skips)
            self.assertFalse(skip_reasons)

    def test_missing_pob_art_uses_base_art_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "65000"
            art_id = "BASE001"
            base_art = os.path.join(tmp, f"{art_id}.pdf")
            with open(base_art, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO20", "art_path": base_art},
                {"template": "PO20B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp, base_art),
                self._build_context("", order_id, tmp, ""),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), base_art)
            self.assertNotIn(1, assignments)
            self.assertIn(1, skips)
            self.assertEqual(skip_reasons.get(1), "Missing extracted PO art")
            self.assertTrue(
                any("Using standard art for PO pair" in msg for msg in logs)
            )

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
            template = "PO15"
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

            assignments, skips, skip_reasons = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertIn(0, assignments)
            self.assertFalse(skips)
            self.assertFalse(skip_reasons)

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

            assignments, skips, skip_reasons = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertFalse(assignments)
            self.assertFalse(skips)
            self.assertFalse(skip_reasons)

    def test_non_po_templates_are_ignored_by_pairing(self):
        entries = [{"template": "P15", "art_path": ""}]
        contexts = [self._build_context("ARTNONPO", "10002", "/tmp")]
        logs: list[str] = []

        assignments, skips, skip_reasons = resolve_paired_page_art(
            entries, contexts, logs.append
        )

        self.assertFalse(assignments)
        self.assertFalse(skips)
        self.assertFalse(skip_reasons)

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

            print_dir = resolve_print_output_folder(
                art_path,
                template,
                "",
                diagnostic=False,
            )
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

    def test_flat_fallback_assigns_unique_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "50000"
            art_id = "ARTFALL01"
            template = "PO1"
            paper = "SBS"

            art_dir = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(art_dir, exist_ok=True)
            art_path = os.path.join(art_dir, "page1.pdf")
            with open(art_path, "w", encoding="utf-8"):
                pass

            print_dir = os.path.join(tmp, order_id, "print")
            os.makedirs(print_dir, exist_ok=True)

            fallback_names = [
                "50000_candidate_first_po1_flat_SBS.pdf",
                "50000_candidate_second_po1_flat_SBS.pdf",
            ]

            filename_base_a = "50000 Candidate A"
            filename_base_b = "50000 Candidate B"

            candidates = [
                {
                    "idx": 0,
                    "filename_base": filename_base_a,
                    "template": template,
                    "paper": paper,
                    "order_id": order_id,
                    "art_id": art_id,
                    "glue": "",
                    "lam": "",
                    "art_path": art_path,
                    "template_path": "",
                    "sample": False,
                    "cut_src": "",
                    "company": "Example Co",
                    "created_by": "Tester",
                },
                {
                    "idx": 1,
                    "filename_base": filename_base_b,
                    "template": template,
                    "paper": paper,
                    "order_id": order_id,
                    "art_id": art_id,
                    "glue": "",
                    "lam": "",
                    "art_path": art_path,
                    "template_path": "",
                    "sample": False,
                    "cut_src": "",
                    "company": "Example Co",
                    "created_by": "Tester",
                },
            ]

            default_paths = {
                os.path.join(print_dir, f"{filename_base_a}_flat_{paper}.pdf"),
                os.path.join(print_dir, f"{filename_base_b}_flat_{paper}.pdf"),
            }

            real_exists = os.path.exists

            def fake_exists(path: str) -> bool:
                if path in default_paths:
                    return False
                return real_exists(path)

            with patch("order_gui.os.listdir", return_value=fallback_names), patch(
                "order_gui.os.path.exists", side_effect=fake_exists
            ):
                flat_entries, sample_entries = prepare_flat_review_entries(
                    candidates,
                    {},
                    [],
                    diagnostic=False,
                )

            self.assertFalse(sample_entries)
            self.assertEqual(len(flat_entries), 2)

            resolved_paths = [entry[1] for entry in flat_entries]
            expected_paths = [os.path.join(print_dir, name) for name in fallback_names]

            self.assertCountEqual(resolved_paths, expected_paths)
            self.assertEqual(len(set(resolved_paths)), 2)


if __name__ == "__main__":
    unittest.main()
