import os
import tempfile
import unittest
import zipfile

from order_gui import format_art_move_summary, move_art_to_folder


class MoveArtTest(unittest.TestCase):
    def test_move_art_to_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_dir = os.path.join(tmp, "12345")
            os.makedirs(order_dir)
            art1 = os.path.join(order_dir, "sample.ai")
            art2 = os.path.join(order_dir, "extra.pdf")
            open(art1, "w").close()
            open(art2, "w").close()

            moved_files, zip_count = move_art_to_folder(order_dir)

            art_dir = os.path.join(order_dir, "art")
            self.assertEqual(moved_files, 2)
            self.assertEqual(zip_count, 0)
            self.assertTrue(os.path.isdir(art_dir))
            self.assertTrue(os.path.isfile(os.path.join(art_dir, "sample.ai")))
            self.assertTrue(os.path.isfile(os.path.join(art_dir, "extra.pdf")))

    def test_move_art_to_folder_extracts_zip_with_loose_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_dir = os.path.join(tmp, "67890")
            os.makedirs(order_dir)
            zip_path = os.path.join(order_dir, "artwork.zip")
            source_file = os.path.join(tmp, "inside.ai")
            with open(source_file, "w", encoding="utf-8") as fh:
                fh.write("dummy")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.write(source_file, arcname="inside.ai")

            moved_files, zip_count = move_art_to_folder(order_dir)

            art_dir = os.path.join(order_dir, "art")
            extracted_dir = os.path.join(art_dir, "artwork")
            self.assertEqual(moved_files, 0)
            self.assertEqual(zip_count, 1)
            self.assertTrue(os.path.isdir(extracted_dir))
            self.assertTrue(os.path.isfile(os.path.join(extracted_dir, "inside.ai")))
            self.assertFalse(os.path.exists(zip_path))
            self.assertNotIn("artwork", os.listdir(order_dir))

    def test_move_art_to_folder_extracts_nested_directory_without_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_dir = os.path.join(tmp, "24680")
            os.makedirs(order_dir)
            zip_path = os.path.join(order_dir, "bundle.zip")

            nested_dir = os.path.join(tmp, "enclosed")
            os.makedirs(nested_dir)
            nested_file = os.path.join(nested_dir, "content.ai")
            with open(nested_file, "w", encoding="utf-8") as fh:
                fh.write("data")

            with zipfile.ZipFile(zip_path, "w") as zf:
                for root, _, files in os.walk(nested_dir):
                    for filename in files:
                        full_path = os.path.join(root, filename)
                        arcname = os.path.relpath(full_path, os.path.dirname(nested_dir))
                        zf.write(full_path, arcname=arcname)

            moved_files, zip_count = move_art_to_folder(order_dir)

            art_dir = os.path.join(order_dir, "art")
            target_dir = os.path.join(art_dir, "enclosed")
            wrapper_dir = os.path.join(art_dir, "bundle")
            self.assertEqual(moved_files, 0)
            self.assertEqual(zip_count, 1)
            self.assertTrue(os.path.isdir(target_dir))
            self.assertFalse(os.path.exists(wrapper_dir))
            self.assertTrue(os.path.isfile(os.path.join(target_dir, "content.ai")))
            self.assertFalse(os.path.exists(zip_path))
            self.assertNotIn("bundle", os.listdir(order_dir))

    def test_format_art_move_summary(self):
        lines, warning = format_art_move_summary(3, 2)
        self.assertEqual(
            lines,
            [
                "Moved 3 art files into art folders.",
                "Extracted 2 archives into dedicated folders.",
            ],
        )
        self.assertEqual(warning, ".zip files were deleted after extraction.")

        lines_single, warning_none = format_art_move_summary(1, 0)
        self.assertEqual(
            lines_single,
            [
                "Moved 1 art file into art folders.",
                "Extracted 0 archives into dedicated folders.",
            ],
        )
        self.assertIsNone(warning_none)


if __name__ == "__main__":
    unittest.main()

