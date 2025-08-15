import unittest
from order_gui import sanitize_filename_base

class FilenameSanitizeTest(unittest.TestCase):
    def test_strip_lines_suffix(self):
        self.assertEqual(sanitize_filename_base('file_lines'), 'file')
        self.assertEqual(sanitize_filename_base('file lines'), 'file')
        self.assertEqual(sanitize_filename_base('guidelines'), 'guidelines')

if __name__ == '__main__':
    unittest.main()
