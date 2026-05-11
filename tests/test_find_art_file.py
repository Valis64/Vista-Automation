import unittest
import tempfile
import os
from order_gui import build_art_name_hint, find_art_file


class FindArtFileTest(unittest.TestCase):
    def test_name_hint_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            art_dir = os.path.join(tmp, "art")
            os.makedirs(art_dir)
            fname = "LB3186_#1.ai"
            open(os.path.join(art_dir, fname), "w").close()
            path = find_art_file(art_dir, "", name_hint="LB3186_#1")
            self.assertEqual(path, os.path.join(art_dir, fname))

    def test_name_hint_finds_pdf_when_art_id_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            art_dir = os.path.join(tmp, "art")
            os.makedirs(art_dir)
            fname = "40359_RT3895G_MC5453H31H_#2.pdf"
            expected = os.path.join(art_dir, fname)
            open(expected, "w").close()

            name_hint = build_art_name_hint(
                {"filename": "40359_RT3895G_MC5453H31H_#2_lines.pdf"},
                {},
            )
            path = find_art_file(art_dir, "", name_hint=name_hint)

            self.assertEqual(name_hint, "40359_RT3895G_MC5453H31H_#2")
            self.assertEqual(path, expected)

    def test_name_hint_finds_month_order_art_when_art_id_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            month_dir = os.path.join(tmp, "month")
            art_dir = os.path.join(month_dir, "40359", "art")
            os.makedirs(art_dir)
            fname = "40359_RT3895G_MC5453H31H_#2.pdf"
            expected = os.path.join(art_dir, fname)
            open(expected, "w").close()

            path = find_art_file(
                "",
                "",
                month_dir,
                "40359",
                "40359_RT3895G_MC5453H31H_#2",
            )

            self.assertEqual(path, expected)

    def test_finds_art_file_in_month_order_art_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            month_dir = os.path.join(tmp, "month")
            art_dir = os.path.join(month_dir, "40359", "art")
            os.makedirs(art_dir)
            fname = "ART-123.ai"
            expected = os.path.join(art_dir, fname)
            open(expected, "w").close()

            path = find_art_file("", "ART-123", month_dir, "40359")

            self.assertEqual(path, expected)

    def test_finds_art_file_directly_in_month_order_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            month_dir = os.path.join(tmp, "month")
            order_dir = os.path.join(month_dir, "40359")
            os.makedirs(order_dir)
            fname = "ART-123.pdf"
            expected = os.path.join(order_dir, fname)
            open(expected, "w").close()

            path = find_art_file("", "ART-123", month_dir, "40359")

            self.assertEqual(path, expected)

    def test_falls_back_to_explicit_root_after_month_order_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            month_dir = os.path.join(tmp, "month")
            order_dir = os.path.join(month_dir, "40359")
            root = os.path.join(tmp, "root")
            os.makedirs(order_dir)
            os.makedirs(root)
            fname = "ART-123.ai"
            expected = os.path.join(root, fname)
            open(expected, "w").close()

            path = find_art_file(root, "ART-123", month_dir, "40359")

            self.assertEqual(path, expected)


if __name__ == "__main__":
    unittest.main()
