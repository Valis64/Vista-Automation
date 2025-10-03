import unittest
import tempfile
import os
from order_gui import find_template_file, extract_paper_type, cut_file_for_template

class TemplateUtilsTest(unittest.TestCase):
    def test_find_template_lowest_paper(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "RT3466_print 10in -vp.ai"), "w").close()
            open(os.path.join(tmp, "RT3466_print_11in.ai"), "w").close()
            open(os.path.join(tmp, "RT3466_print 13in -vp.ai"), "w").close()
            result = find_template_file(tmp, "RT3466")
            self.assertTrue(result.endswith("10in -vp.ai"))

    def test_extract_paper_type(self):
        self.assertEqual(extract_paper_type("RT3466_print 10in -vp.pdf"), "10in")
        self.assertEqual(extract_paper_type("RT3466_11in_print.ai"), "11in")
        self.assertEqual(extract_paper_type("no_paper.pdf"), "")

    def test_sample_template_and_cut_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = "RT3466_print 10in -vp (SAMPLE).pdf"
            print_path = os.path.join(tmp, base)
            cut_path = os.path.join(tmp, "RT3466_cut 10in.pdf")
            open(print_path, "w").close()
            open(cut_path, "w").close()
            result = find_template_file(tmp, "RT3466", sample=True)
            self.assertEqual(result, print_path)
            self.assertEqual(cut_file_for_template(result), cut_path)

if __name__ == "__main__":
    unittest.main()
