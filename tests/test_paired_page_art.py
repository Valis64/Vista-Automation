import os
import tempfile
import time
import unittest
from unittest.mock import patch
import fitz

from order_gui import (
    find_template_file,
    prepare_flat_review_entries,
    resolve_print_output_folder,
    sanitize_filename_base,
)
from review import BLANK_TEMPLATE_ART_SENTINEL
from utils.po_art import resolve_paired_page_art


class ResolvePairedPageArtTests(unittest.TestCase):
    def _build_context(
        self,
        art_id: str,
        order_id: str,
        month_root: str,
        art_path: str = "",
        *,
        qty: int = 0,
        sample: bool = False,
    ) -> dict:
        return {
            "art_id": art_id,
            "order_id": order_id,
            "month_root": month_root,
            "art_root": "",
            "art_path": art_path,
            "template": "",
            "qty": qty,
            "sample": sample,
        }

    def test_maps_pages_for_base_and_mate(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "12345"
            art_id = "ART001"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            page1 = os.path.join(folder, f"{art_id}_page1.pdf")
            page2 = os.path.join(folder, f"{art_id}_page2.pdf")
            with open(page1, "w", encoding="utf-8"):
                pass
            with open(page2, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO1", "art_path": ""},
                {"template": "PO1B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp, qty=11, sample=True),
                self._build_context(art_id, order_id, tmp, qty=11, sample=True),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
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
            page1 = os.path.join(folder, f"{art_id}_page1.pdf")
            with open(page1, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO2", "art_path": ""},
                {"template": "PO2B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp, qty=11, sample=True),
                self._build_context(art_id, order_id, tmp, qty=11, sample=True),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), page1)
            self.assertIn(1, skips)
            self.assertEqual(skip_reasons.get(1), "Missing page2.pdf")
            self.assertTrue(any("page2.pdf not found" in msg for msg in logs))

    def test_missing_page2_marks_blank_template_when_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "54321"
            art_id = "ART002"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            page1 = os.path.join(folder, f"{art_id}_page1.pdf")
            with open(page1, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO2", "art_path": ""},
                {"template": "PO2B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp, qty=11, sample=True),
                self._build_context(art_id, order_id, tmp, qty=11, sample=True),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, blank_template_indices = resolve_paired_page_art(
                entries,
                contexts,
                logs.append,
                no_page2_policy="blank_template",
            )

            self.assertEqual(assignments.get(0), page1)
            self.assertNotIn(1, assignments)
            self.assertIn(1, blank_template_indices)
            self.assertNotIn(1, skips)
            self.assertNotIn(1, skip_reasons)
            self.assertTrue(any("page2.pdf not found" in msg for msg in logs))
            self.assertTrue(any("blank-template output" in msg for msg in logs))

    def test_missing_page2_marks_blank_template_with_configured_sample_quantity(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "54323"
            art_id = "ART101"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            page1 = os.path.join(folder, f"{art_id}_page1.pdf")
            with open(page1, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO2", "art_path": ""},
                {"template": "PO2B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp, qty=101, sample=False),
                self._build_context(art_id, order_id, tmp, qty=101, sample=False),
            ]
            for context in contexts:
                context["sample_quantity"] = 101
            logs: list[str] = []

            assignments, skips, skip_reasons, blank_template_indices = resolve_paired_page_art(
                entries,
                contexts,
                logs.append,
                no_page2_policy="blank_template",
            )

            self.assertEqual(assignments.get(0), page1)
            self.assertNotIn(1, assignments)
            self.assertIn(1, blank_template_indices)
            self.assertNotIn(1, skips)
            self.assertNotIn(1, skip_reasons)
            self.assertTrue(any("blank-template output" in msg for msg in logs))

    def test_missing_page2_non_sample_skips_even_when_blank_policy_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "54322"
            art_id = "ART002A"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            page1 = os.path.join(folder, f"{art_id}_page1.pdf")
            with open(page1, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO2", "art_path": ""},
                {"template": "PO2B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp, qty=250, sample=False),
                self._build_context(art_id, order_id, tmp, qty=250, sample=False),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, blank_template_indices = resolve_paired_page_art(
                entries,
                contexts,
                logs.append,
                no_page2_policy="blank_template",
            )

            self.assertEqual(assignments.get(0), page1)
            self.assertIn(1, skips)
            self.assertEqual(skip_reasons.get(1), "Missing page2.pdf")
            self.assertNotIn(1, blank_template_indices)
            self.assertTrue(any("page2.pdf not found" in msg for msg in logs))
            self.assertFalse(any("blank-template output" in msg for msg in logs))

    def test_missing_mate_logs_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "88888"
            art_id = "ART003"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            page1 = os.path.join(folder, f"{art_id}_page1.pdf")
            with open(page1, "w", encoding="utf-8"):
                pass

            entries = [{"template": "PO3", "art_path": ""}]
            contexts = [self._build_context(art_id, order_id, tmp)]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
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
            page1 = os.path.join(folder, f"{art_id}_PaGe1.PDF")
            page2 = os.path.join(folder, f"{art_id}_PAGE2.PDF")
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

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), page1)
            self.assertEqual(assignments.get(1), page2)
            self.assertFalse(skips)
            self.assertFalse(skip_reasons)

    def test_prefers_stemmed_pages_when_legacy_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "55555"
            art_id = "ARTPREF"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            preferred_page1 = os.path.join(folder, f"{art_id}_page1.pdf")
            preferred_page2 = os.path.join(folder, f"{art_id}_page2.pdf")
            legacy_page1 = os.path.join(folder, "page1.pdf")
            legacy_page2 = os.path.join(folder, "page2.pdf")
            for path in (preferred_page1, preferred_page2, legacy_page1, legacy_page2):
                with open(path, "w", encoding="utf-8"):
                    pass

            entries = [
                {"template": "PO7", "art_path": ""},
                {"template": "PO7B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp),
                self._build_context(art_id, order_id, tmp),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), preferred_page1)
            self.assertEqual(assignments.get(1), preferred_page2)
            self.assertFalse(skips)
            self.assertFalse(skip_reasons)

    def test_legacy_page_names_are_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "77778"
            art_id = "ARTLEG"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)
            page1 = os.path.join(folder, "page1.pdf")
            page2 = os.path.join(folder, "page2.pdf")
            for path in (page1, page2):
                with open(path, "w", encoding="utf-8"):
                    pass

            entries = [
                {"template": "POX", "art_path": ""},
                {"template": "POXB", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp),
                self._build_context(art_id, order_id, tmp),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
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
                self._build_context(art_id, order_id, tmp, base_art, qty=11, sample=True),
                self._build_context("", order_id, tmp, "", qty=11, sample=True),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), base_art)
            self.assertNotIn(1, assignments)
            self.assertIn(1, skips)
            self.assertEqual(skip_reasons.get(1), "Missing extracted PO art")
            self.assertTrue(
                any("Using standard art for PO pair" in msg for msg in logs)
            )

    def test_single_page_pdf_handles_mate_by_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "70001"
            art_id = "SINGLEPAGE"
            base_art = os.path.join(tmp, f"{art_id}.pdf")
            doc = fitz.open()
            try:
                doc.new_page()
                doc.save(base_art)
            finally:
                doc.close()

            entries = [
                {"template": "PO21", "art_path": base_art},
                {"template": "PO21B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp, base_art, qty=11, sample=True),
                self._build_context("", order_id, tmp, "", qty=11, sample=True),
            ]
            for (
                no_page2_policy,
                expected_skips,
                expected_blank_templates,
                expected_log_text,
            ) in (
                ("skip", {1}, set(), "skipping template"),
                ("blank_template", set(), {1}, "blank-template output"),
            ):
                with self.subTest(no_page2_policy=no_page2_policy):
                    logs: list[str] = []
                    assignments, skips, skip_reasons, blank_template_indices = (
                        resolve_paired_page_art(
                            entries,
                            contexts,
                            logs.append,
                            no_page2_policy=no_page2_policy,
                        )
                    )

                    self.assertEqual(assignments.get(0), base_art)
                    self.assertEqual(skips, expected_skips)
                    self.assertEqual(blank_template_indices, expected_blank_templates)
                    if no_page2_policy == "skip":
                        self.assertEqual(skip_reasons.get(1), "No page 2 art")
                    else:
                        self.assertNotIn(1, skip_reasons)
                    self.assertTrue(
                        any("has only 1 page" in msg for msg in logs),
                        msg=f"Logs missing warning: {logs}",
                    )
                    self.assertTrue(
                        any(expected_log_text in msg for msg in logs),
                        msg=f"Logs missing '{expected_log_text}' warning: {logs}",
                    )

    def test_prefers_unsuffixed_single_page_over_page1(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "71000"
            art_id = "UNSUFFIXED"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)

            unsuffixed = os.path.join(folder, f"{art_id}.pdf")
            page1 = os.path.join(folder, f"{art_id}_page1.pdf")
            for path in (unsuffixed, page1):
                doc = fitz.open()
                try:
                    doc.new_page()
                    doc.save(path)
                finally:
                    doc.close()

            entries = [
                {"template": "PO30", "art_path": ""},
                {"template": "PO30B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp),
                self._build_context(art_id, order_id, tmp),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), unsuffixed)
            self.assertIn(1, skips)
            self.assertEqual(skip_reasons.get(1), "Missing page2.pdf")
            self.assertTrue(any("Resolved zip folder" in msg for msg in logs))

    def test_unsuffixed_selected_when_other_page1_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "71500"
            art_id = "RIGHT_ONE"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)

            unsuffixed = os.path.join(folder, f"{art_id}.pdf")
            other_page1 = os.path.join(folder, "OTHER_page1.pdf")

            doc = fitz.open()
            try:
                doc.new_page()
                doc.save(unsuffixed)
            finally:
                doc.close()

            with open(other_page1, "w", encoding="utf-8"):
                pass

            entries = [{"template": "PO31", "art_path": ""}]
            contexts = [self._build_context(art_id, order_id, tmp)]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), unsuffixed)
            self.assertNotEqual(assignments.get(0), other_page1)
            self.assertFalse(skips)
            self.assertFalse(skip_reasons)

    def test_rejects_page1_from_other_art_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "72000"
            art_id = "RIGHTID"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)

            wrong_page = os.path.join(folder, "WRONG_page1.pdf")
            with open(wrong_page, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO31", "art_path": ""},
                {"template": "PO31B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp),
                self._build_context(art_id, order_id, tmp),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertFalse(assignments)
            self.assertIn(0, skips)
            self.assertIn(1, skips)
            self.assertEqual(skip_reasons.get(0), "No PO art found")
            self.assertEqual(skip_reasons.get(1), "No PO art found")

    def test_single_page_unsuffixed_skips_mate_with_other_page1_nearby(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "72500"
            art_id = "SINGLE_NEARBY"
            folder = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(folder, exist_ok=True)

            unsuffixed = os.path.join(folder, f"{art_id}.pdf")
            other_page1 = os.path.join(folder, "NEIGHBOR_page1.pdf")

            doc = fitz.open()
            try:
                doc.new_page()
                doc.save(unsuffixed)
            finally:
                doc.close()

            with open(other_page1, "w", encoding="utf-8"):
                pass

            entries = [
                {"template": "PO32", "art_path": ""},
                {"template": "PO32B", "art_path": ""},
            ]
            contexts = [
                self._build_context(art_id, order_id, tmp),
                self._build_context(art_id, order_id, tmp),
            ]
            logs: list[str] = []

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertEqual(assignments.get(0), unsuffixed)
            self.assertNotIn(other_page1, assignments.values())
            self.assertNotIn(1, assignments)
            self.assertIn(1, skips)
            self.assertEqual(skip_reasons.get(1), "Missing page2.pdf")

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
            page1 = os.path.join(art_folder, f"{art_id}_page1.pdf")
            page2 = os.path.join(art_folder, f"{art_id}_page2.pdf")
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

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
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

    def test_review_prefers_assigned_page_over_candidate_art(self):
        with tempfile.TemporaryDirectory() as tmp:
            assigned_page = os.path.join(tmp, "art_page1.pdf")
            with open(assigned_page, "w", encoding="utf-8"):
                pass

            candidates = [
                {
                    "idx": 0,
                    "filename_base": "Sample",
                    "template": "PO001",
                    "paper": "SBS",
                    "order_id": "10001",
                    "art_id": "POART",
                    "glue": "",
                    "lam": "",
                    "art_path": os.path.join(tmp, "original.pdf"),
                    "template_path": "",
                    "sample": False,
                    "cut_src": "",
                }
            ]

            assignments = {0: assigned_page}
            flat_entries, _ = prepare_flat_review_entries(
                candidates, assignments, [], diagnostic=False
            )

            self.assertEqual(len(flat_entries), 1)
            _, _, info = flat_entries[0]
            self.assertEqual(info[-1], assigned_page)

    def test_blank_template_entry_uses_blank_art_sentinel(self):
        with tempfile.TemporaryDirectory() as tmp:
            assigned_page = os.path.join(tmp, "art_page1.pdf")
            with open(assigned_page, "w", encoding="utf-8"):
                pass

            candidates = [
                {
                    "idx": 0,
                    "filename_base": "Sample",
                    "template": "PO001",
                    "paper": "SBS",
                    "order_id": "10001",
                    "art_id": "POART",
                    "glue": "",
                    "lam": "",
                    "art_path": os.path.join(tmp, "original.pdf"),
                    "template_path": "",
                    "sample": False,
                    "cut_src": "",
                }
            ]

            assignments = {0: assigned_page}
            flat_entries, _ = prepare_flat_review_entries(
                candidates,
                assignments,
                [],
                blank_template_indices={0},
                diagnostic=False,
            )

            self.assertEqual(len(flat_entries), 1)
            _, _, info = flat_entries[0]
            self.assertEqual(info[-1], BLANK_TEMPLATE_ART_SENTINEL)

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

            assignments, skips, skip_reasons, _ = resolve_paired_page_art(
                entries, contexts, logs.append
            )

            self.assertFalse(assignments)
            self.assertFalse(skips)
            self.assertFalse(skip_reasons)

    def test_non_po_templates_are_ignored_by_pairing(self):
        entries = [{"template": "P15", "art_path": ""}]
        contexts = [self._build_context("ARTNONPO", "10002", "/tmp")]
        logs: list[str] = []

        assignments, skips, skip_reasons, _ = resolve_paired_page_art(
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
                f"50000_{art_id}_candidate_alpha_po1_flat_SBS.pdf",
                f"50000_{art_id}_candidate_beta_po1_flat_SBS.pdf",
            ]

            filename_base_a = "50000 Candidate Alpha"
            filename_base_b = "50000 Candidate Beta"

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

    def test_flat_fallback_requires_recent_run_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_id = "50500"
            art_id = "ARTRECENT"
            template = "PO1"
            paper = "SBS"

            art_dir = os.path.join(tmp, order_id, "art", art_id)
            os.makedirs(art_dir, exist_ok=True)
            art_path = os.path.join(art_dir, "page1.pdf")
            with open(art_path, "w", encoding="utf-8"):
                pass

            print_dir = resolve_print_output_folder(
                art_path,
                template,
                "",
                diagnostic=False,
            )
            os.makedirs(print_dir, exist_ok=True)

            old_name = f"{order_id}_{art_id}_old_candidate_flat_SBS.pdf"
            new_name = f"{order_id}_{art_id}_new_candidate_flat_SBS.pdf"
            old_path = os.path.join(print_dir, old_name)
            new_path = os.path.join(print_dir, new_name)
            for path in (old_path, new_path):
                with open(path, "w", encoding="utf-8"):
                    pass

            run_start_time = time.time()
            os.utime(old_path, (run_start_time - 10, run_start_time - 10))
            os.utime(new_path, (run_start_time + 10, run_start_time + 10))

            candidates = [
                {
                    "idx": 0,
                    "filename_base": "50500 Candidate",
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
                }
            ]

            flat_entries, sample_entries = prepare_flat_review_entries(
                candidates,
                {},
                [],
                run_start_time=run_start_time,
                diagnostic=False,
            )

            self.assertFalse(sample_entries)
            self.assertEqual(len(flat_entries), 1)
            _, flat_path, info = flat_entries[0]
            expected_path = os.path.join(print_dir, new_name)

            self.assertEqual(flat_path, expected_path)
            self.assertEqual(info[0], expected_path)


if __name__ == "__main__":
    unittest.main()
