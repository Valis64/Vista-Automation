import unittest
from pathlib import Path

from order_gui import (
    DIAGNOSTIC_PRINT_FOLDER_NAME,
    PRINT_FOLDER_NAME,
    resolve_print_output_folder,
)


class ResolvePrintFolderTest(unittest.TestCase):
    def setUp(self):
        self.order_root = Path("/tmp/base/YBS/Vista/35198")
        self.art_path = self.order_root / "art" / "sample.ai"
        self.nested_p_art_path = (
            self.order_root / "art" / "12345" / "P01" / "page1.pdf"
        )

    def test_standard_template_uses_order_folder(self):
        folder = resolve_print_output_folder(str(self.art_path), template_code="RT3711")
        self.assertEqual(Path(folder), self.order_root / PRINT_FOLDER_NAME)

    def test_p_template_code_uses_order_folder(self):
        folder = resolve_print_output_folder(str(self.art_path), template_code="PZ999")
        self.assertEqual(Path(folder), self.order_root / PRINT_FOLDER_NAME)

    def test_p_template_filename_fallback(self):
        folder = resolve_print_output_folder(
            str(self.art_path), template_code="", template_filename="Ptemplate.ai"
        )
        self.assertEqual(Path(folder), self.order_root / PRINT_FOLDER_NAME)

    def test_diagnostic_folder_name_preserved(self):
        folder = resolve_print_output_folder(
            str(self.art_path), template_code="PZ999", diagnostic=True
        )
        self.assertEqual(
            Path(folder), self.order_root / DIAGNOSTIC_PRINT_FOLDER_NAME
        )

    def test_nested_p_art_path_resolves_to_order_print_folder(self):
        folder = resolve_print_output_folder(
            str(self.nested_p_art_path), template_code="P01"
        )
        self.assertEqual(Path(folder), self.order_root / PRINT_FOLDER_NAME)


if __name__ == "__main__":
    unittest.main()
