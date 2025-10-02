import tempfile
import unittest
import zipfile
from pathlib import Path

from order_gui import move_art_to_folder


class MoveArtTest(unittest.TestCase):
    def test_move_art_to_folder_moves_loose_art(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_dir = Path(tmp) / "12345"
            order_dir.mkdir()
            art1 = order_dir / "sample.ai"
            art2 = order_dir / "extra.pdf"
            art1.touch()
            art2.touch()

            moved, processed = move_art_to_folder(str(order_dir))

            art_dir = order_dir / "art"
            self.assertEqual((moved, processed), (2, 0))
            self.assertTrue(art_dir.is_dir())
            self.assertTrue((art_dir / "sample.ai").is_file())
            self.assertTrue((art_dir / "extra.pdf").is_file())

    def test_move_art_to_folder_extracts_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_dir = Path(tmp) / "54321"
            order_dir.mkdir()
            zip_path = order_dir / "art_archive.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("folder/nested.ai", "")
                zf.writestr("nested/deep/file.pdf", "")

            moved, processed = move_art_to_folder(str(order_dir))

            art_dir = order_dir / "art"
            extracted_dir = art_dir / "art_archive"

            self.assertEqual((moved, processed), (2, 1))
            self.assertTrue(extracted_dir.is_dir())
            self.assertTrue((extracted_dir / "folder" / "nested.ai").is_file())
            self.assertTrue((extracted_dir / "nested" / "deep" / "file.pdf").is_file())
            self.assertFalse(zip_path.exists())


if __name__ == "__main__":
    unittest.main()

