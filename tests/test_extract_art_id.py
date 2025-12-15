import unittest
from order_gui import extract_art_id

class ExtractArtIdTest(unittest.TestCase):
    def test_underscore_format(self):
        text = "RTVista01G_MB029EE5CB_FG0541G892"
        self.assertEqual(extract_art_id(text), "MB029EE5CB")

    def test_prefers_first_art_code_with_prefix_present(self):
        text = "RTVista01G AA11BB22CC ZZ99YY88XX"
        self.assertEqual(extract_art_id(text), "AA11BB22CC")

    def test_prefers_first_art_code(self):
        text = "AA11BB22CC ZZ99YY88XX"
        self.assertEqual(extract_art_id(text), "AA11BB22CC")

    def test_filename_format(self):
        text = "34516_RT3710S_M97D390872_#6"
        self.assertEqual(extract_art_id(text), "M97D390872")

if __name__ == "__main__":
    unittest.main()
