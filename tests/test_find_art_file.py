import os
import tempfile
import unittest

from order_gui import find_art_file

class FindArtFileTest(unittest.TestCase):
    def test_name_hint_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            art_dir = os.path.join(tmp, "art")
            os.makedirs(art_dir)
            fname = "LB3186_#1.ai"
            open(os.path.join(art_dir, fname), "w").close()
            path = find_art_file(art_dir, "", name_hint="LB3186_#1")
            self.assertEqual(path, os.path.join(art_dir, fname))

    def test_tray_sleeve_pages_from_month_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            month_dir = os.path.join(tmp, "2024-01")
            art_id = "TS1001"
            art_dir = os.path.join(month_dir, "12345", "art", art_id)
            os.makedirs(art_dir)
            page1_file = os.path.join(art_dir, "page1.pdf")
            page2_file = os.path.join(art_dir, "page2.pdf")
            open(page1_file, "w").close()
            open(page2_file, "w").close()

            front = find_art_file(
                "",
                art_id,
                month_dir=month_dir,
                order_id="12345",
                template_code="P001",
            )
            back = find_art_file(
                "",
                art_id,
                month_dir=month_dir,
                order_id="12345",
                template_code="P001B",
            )

            self.assertEqual(front, page1_file)
            self.assertEqual(back, page2_file)

    def test_tray_sleeve_pages_from_art_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            art_root = os.path.join(tmp, "art_root")
            art_id = "TS2002"
            art_dir = os.path.join(art_root, art_id)
            os.makedirs(art_dir)
            page1_file = os.path.join(art_dir, "page1.pdf")
            page2_file = os.path.join(art_dir, "page2.pdf")
            open(page1_file, "w").close()
            open(page2_file, "w").close()

            front = find_art_file(art_root, art_id, template_code="P010")
            back = find_art_file(art_root, art_id, template_code="P010B")

            self.assertEqual(front, page1_file)
            self.assertEqual(back, page2_file)

    def test_tray_sleeve_pages_from_nested_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            month_dir = os.path.join(tmp, "2024-02")
            art_id = "TS3003"
            page1_dir = os.path.join(month_dir, "54321", "art", art_id, "Page 1")
            page2_dir = os.path.join(month_dir, "54321", "art", art_id, "Page 2")
            os.makedirs(page1_dir)
            os.makedirs(page2_dir)
            page1_file = os.path.join(page1_dir, "Page 1.ai")
            page2_file = os.path.join(page2_dir, "Page 2.ai")
            open(page1_file, "w").close()
            open(page2_file, "w").close()

            front = find_art_file(
                "",
                art_id,
                month_dir=month_dir,
                order_id="54321",
                template_code="P020",
            )
            back = find_art_file(
                "",
                art_id,
                month_dir=month_dir,
                order_id="54321",
                template_code="P020B",
            )

            self.assertEqual(front, page1_file)
            self.assertEqual(back, page2_file)

if __name__ == "__main__":
    unittest.main()
