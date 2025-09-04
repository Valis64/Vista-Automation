import unittest
from order_gui import extract_art_id

class ExtractArtIdTest(unittest.TestCase):
    def test_underscore_format(self):
        text = "RTVista01G_MB029EE5CB_FG0541G892"
        self.assertEqual(extract_art_id(text), "MB029EE5CB")

    def test_filename_format(self):
        text = "34516_RT3710S_M97D390872_#6"
        self.assertEqual(extract_art_id(text), "M97D390872")

if __name__ == "__main__":
    unittest.main()
