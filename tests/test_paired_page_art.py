import os
import tempfile
import unittest

from order_gui import resolve_paired_page_art, find_template_file


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


if __name__ == "__main__":
    unittest.main()
