import unittest
import tempfile
import os
from order_gui import write_paper_summary

class PaperSummaryTest(unittest.TestCase):
    def test_summary_files_created(self):
        pairs = [
            {"order_id": "123", "paperType": "10in"},
            {"order_id": "123", "paperType": "12in"},
            {"order_id": "456", "paperType": "11in"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_paper_summary(pairs, tmp)
            self.assertEqual(len(paths), 2)
            with open(os.path.join(tmp, "123_paper_types.txt")) as f:
                lines = [l.strip() for l in f if l.strip()]
            self.assertEqual(sorted(lines), ["10in", "12in"])
            with open(os.path.join(tmp, "456_paper_types.txt")) as f:
                lines = [l.strip() for l in f if l.strip()]
            self.assertEqual(lines, ["11in"])

if __name__ == "__main__":
    unittest.main()
