import unittest
from pathlib import Path

from order_gui import (
    DIAGNOSTIC_PRINT_FOLDER_NAME,
    PRINT_FOLDER_NAME,
    resolve_print_output_folder,
)


class ResolvePrintFolderTest(unittest.TestCase):
    def setUp(self):
        self.art_path = Path("/tmp/base/YBS/Vista/35198/art/sample.ai")

    def test_standard_template_uses_order_folder(self):
        folder = resolve_print_output_folder(str(self.art_path), template_code="RT3711")
        self.assertEqual(Path(folder), self.art_path.parents[1] / PRINT_FOLDER_NAME)

    def test_pb_template_code_uses_order_folder(self):
        folder = resolve_print_output_folder(str(self.art_path), template_code="PB004")
        self.assertEqual(Path(folder), self.art_path.parents[1] / PRINT_FOLDER_NAME)

    def test_pb_template_filename_uses_order_folder(self):
        folder = resolve_print_output_folder(
            str(self.art_path), template_filename="PB004_template.ai"
        )
        self.assertEqual(Path(folder), self.art_path.parents[1] / PRINT_FOLDER_NAME)

    def test_po_template_uses_order_folder_when_under_art(self):
        folder = resolve_print_output_folder(str(self.art_path), template_code="PO123")
        self.assertEqual(Path(folder), self.art_path.parents[1] / PRINT_FOLDER_NAME)

    def test_po_template_uses_two_levels_up_for_extracted_pages(self):
        extracted_page = self.art_path.parent / "ART001" / "ART001_page1.pdf"
        folder = resolve_print_output_folder(str(extracted_page), template_code="PO123")
        self.assertEqual(Path(folder), extracted_page.parents[2] / PRINT_FOLDER_NAME)

    def test_po_blank_template_missing_page2_uses_page1_order_print_folder(self):
        page1_art = self.art_path.parent / "ART002" / "ART002_page1.pdf"
        folder = resolve_print_output_folder(str(page1_art), template_code="PO2B")
        self.assertEqual(Path(folder), page1_art.parents[2] / PRINT_FOLDER_NAME)

    def test_po_template_keeps_one_level_up_for_standard_art_subfolders(self):
        nested_art = self.art_path.parent / "ART001" / "art_file.pdf"
        folder = resolve_print_output_folder(str(nested_art), template_code="PO123")
        self.assertEqual(Path(folder), nested_art.parents[1] / PRINT_FOLDER_NAME)

    def test_p_template_code_uses_art_parent(self):
        folder = resolve_print_output_folder(str(self.art_path), template_code="PZ999")
        self.assertEqual(Path(folder), self.art_path.parents[1] / PRINT_FOLDER_NAME)

    def test_p_template_filename_fallback_uses_art_parent(self):
        folder = resolve_print_output_folder(
            str(self.art_path), template_code="", template_filename="Ptemplate.ai"
        )
        self.assertEqual(Path(folder), self.art_path.parents[1] / PRINT_FOLDER_NAME)

    def test_diagnostic_folder_name_preserved(self):
        folder = resolve_print_output_folder(
            str(self.art_path), template_code="PZ999", diagnostic=True
        )
        self.assertEqual(
            Path(folder), self.art_path.parents[1] / DIAGNOSTIC_PRINT_FOLDER_NAME
        )


if __name__ == "__main__":
    unittest.main()
