import unittest
import tempfile
import os
import zipfile

from order_gui import move_art_to_folder


class MoveArtTest(unittest.TestCase):
    def test_move_art_to_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_dir = os.path.join(tmp, "12345")
            os.makedirs(order_dir)
            art1 = os.path.join(order_dir, "sample.ai")
            art2 = os.path.join(order_dir, "extra.pdf")
            open(art1, "w").close()
            open(art2, "w").close()

            result = move_art_to_folder(order_dir)

            art_dir = os.path.join(order_dir, "art")
            self.assertEqual(result.moved, 2)
            self.assertEqual(result.extracted_files, 0)
            self.assertEqual(result.extracted_archives, 0)
            self.assertTrue(os.path.isdir(art_dir))
            self.assertTrue(os.path.isfile(os.path.join(art_dir, "sample.ai")))
            self.assertTrue(os.path.isfile(os.path.join(art_dir, "extra.pdf")))

    def test_extracts_zip_to_unique_art_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_dir = os.path.join(tmp, "67890")
            os.makedirs(order_dir)
            zip_path = os.path.join(order_dir, "bundle.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("file.txt", "content")

            result = move_art_to_folder(order_dir)

            art_dir = os.path.join(order_dir, "art")
            extracted_file = os.path.join(art_dir, "bundle", "file.txt")
            self.assertEqual(result.moved, 0)
            self.assertEqual(result.extracted_files, 1)
            self.assertEqual(result.extracted_archives, 1)
            self.assertTrue(os.path.isdir(os.path.join(art_dir, "bundle")))
            self.assertTrue(os.path.isfile(extracted_file))
            self.assertFalse(os.path.exists(zip_path))


if __name__ == "__main__":
    unittest.main()

