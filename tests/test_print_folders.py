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

    def test_p_template_code_uses_two_levels_up(self):
        folder = resolve_print_output_folder(str(self.art_path), template_code="PZ999")
        self.assertEqual(Path(folder), self.art_path.parents[2] / PRINT_FOLDER_NAME)

    def test_pb_template_code_stays_order_folder(self):
        folder = resolve_print_output_folder(str(self.art_path), template_code="PB123")
        self.assertEqual(Path(folder), self.art_path.parents[1] / PRINT_FOLDER_NAME)

    def test_p_template_filename_fallback(self):
        folder = resolve_print_output_folder(
            str(self.art_path), template_code="", template_filename="PZ999.ai"
        )
        self.assertEqual(Path(folder), self.art_path.parents[2] / PRINT_FOLDER_NAME)

    def test_pb_template_filename_fallback_prefers_order_folder(self):
        folder = resolve_print_output_folder(
            str(self.art_path), template_code="", template_filename="PB123-template.ai"
        )
        self.assertEqual(Path(folder), self.art_path.parents[1] / PRINT_FOLDER_NAME)

    def test_pb_pair_filename_with_prefix_stays_in_order_folder(self):
        folder = resolve_print_output_folder(
            str(self.art_path), template_code="", template_filename="Paired Template PB123.ai"
        )
        self.assertEqual(Path(folder), self.art_path.parents[1] / PRINT_FOLDER_NAME)

    def test_diagnostic_folder_name_preserved(self):
        folder = resolve_print_output_folder(
            str(self.art_path), template_code="PZ999", diagnostic=True
        )
        self.assertEqual(
            Path(folder), self.art_path.parents[2] / DIAGNOSTIC_PRINT_FOLDER_NAME
        )


if __name__ == "__main__":
    unittest.main()
