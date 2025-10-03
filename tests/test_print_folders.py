import unittest
from pathlib import Path

from order_gui import (
    DIAGNOSTIC_PRINT_FOLDER_NAME,
    PRINT_FOLDER_NAME,
    resolve_print_output_folder,
)


class ResolvePrintFolderTest(unittest.TestCase):
    def setUp(self):
        self.order_dir = Path("/tmp/base/YBS/Vista/35198")
        self.flat_art_path = self.order_dir / "art" / "sample.ai"
        self.nested_art_path = self.order_dir / "art" / "nested" / "page1.pdf"

    def test_standard_template_uses_order_folder(self):
        folder = resolve_print_output_folder(
            str(self.flat_art_path), template_code="RT3711"
        )
        self.assertEqual(Path(folder), self.flat_art_path.parents[1] / PRINT_FOLDER_NAME)

    def test_p_template_code_uses_two_levels_up(self):
        folder = resolve_print_output_folder(
            str(self.nested_art_path), template_code="PZ999"
        )
        self.assertEqual(Path(folder), self.order_dir / PRINT_FOLDER_NAME)

    def test_p_template_filename_fallback(self):
        folder = resolve_print_output_folder(
            str(self.nested_art_path), template_code="", template_filename="Ptemplate.ai"
        )
        self.assertEqual(Path(folder), self.order_dir / PRINT_FOLDER_NAME)

    def test_p_template_flat_art_path(self):
        folder = resolve_print_output_folder(
            str(self.flat_art_path), template_code="PZ999"
        )
        self.assertEqual(Path(folder), self.order_dir / PRINT_FOLDER_NAME)

    def test_diagnostic_folder_name_preserved(self):
        folder = resolve_print_output_folder(
            str(self.nested_art_path), template_code="PZ999", diagnostic=True
        )
        self.assertEqual(Path(folder), self.order_dir / DIAGNOSTIC_PRINT_FOLDER_NAME)


if __name__ == "__main__":
    unittest.main()
