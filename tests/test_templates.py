import unittest
import tempfile
import os
from order_gui import (
    _resolve_template_and_paper,
    cut_file_for_template,
    extract_paper_type,
    find_template_file,
)

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

    def test_sample_template_selected_without_legacy_sample_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample_dir = os.path.join(tmp, "Sample Templates")
            os.makedirs(sample_dir, exist_ok=True)
            sample_path = os.path.join(sample_dir, "RT3466_print 10in -vp.pdf")
            open(sample_path, "w").close()
            result = find_template_file(tmp, "RT3466", sample=True)
            self.assertEqual(result, sample_path)

    def test_non_sample_template_ignores_sample_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample_dir = os.path.join(tmp, "samples")
            os.makedirs(sample_dir, exist_ok=True)
            open(os.path.join(sample_dir, "RT3466_print 10in -vp.pdf"), "w").close()
            standard_path = os.path.join(tmp, "RT3466_print 11in -vp.ai")
            open(standard_path, "w").close()
            result = find_template_file(tmp, "RT3466", sample=False)
            self.assertEqual(result, standard_path)

    def test_template_code_matching_prefers_exact_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            exact = os.path.join(tmp, "RT3466_print 11in -vp.ai")
            similar = os.path.join(tmp, "RT34660_print 10in -vp.ai")
            open(exact, "w").close()
            open(similar, "w").close()
            result = find_template_file(tmp, "RT3466")
            self.assertEqual(result, exact)

    def test_resolve_template_and_paper_non_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            standard_path = os.path.join(tmp, "RT3466_print 11in -vp.ai")
            open(standard_path, "w").close()
            path, paper = _resolve_template_and_paper(
                tmp,
                "RT3466",
                {"gluetab": "- [250]"},
            )
            self.assertEqual(path, standard_path)
            self.assertEqual(paper, "11in")

    def test_resolve_template_and_paper_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample_dir = os.path.join(tmp, "Sample Templates")
            os.makedirs(sample_dir, exist_ok=True)
            sample_path = os.path.join(sample_dir, "RT3466_print 10in -vp.ai")
            open(sample_path, "w").close()
            path, paper = _resolve_template_and_paper(
                tmp,
                "RT3466",
                {"gluetab": "- [11]"},
            )
            self.assertEqual(path, sample_path)
            self.assertEqual(paper, "10in")

    def test_resolve_template_and_paper_matches_save_ui_processing_contexts(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "samples"), exist_ok=True)
            sample_path = os.path.join(tmp, "samples", "RT3466_print 10in -vp.pdf")
            regular_path = os.path.join(tmp, "RT3466_print 11in -vp.pdf")
            open(sample_path, "w").close()
            open(regular_path, "w").close()

            base_item = {"template_dir": tmp, "template": "RT3466"}
            contexts = {
                "ui": {**base_item, "gluetab": "- [11]"},
                "save": {**base_item, "gluetab": "- [11]", "order_id": "100"},
                "processing": {**base_item, "gluetab": "- [11]", "art_id": "A1"},
            }
            sample_results = {
                key: _resolve_template_and_paper(tmp, "RT3466", ctx)[1]
                for key, ctx in contexts.items()
            }
            self.assertEqual(set(sample_results.values()), {"10in"})

            non_sample_contexts = {
                "ui": {**base_item, "gluetab": "- [250]"},
                "save": {**base_item, "gluetab": "- [250]", "order_id": "100"},
                "processing": {**base_item, "gluetab": "- [250]", "art_id": "A1"},
            }
            non_sample_results = {
                key: _resolve_template_and_paper(tmp, "RT3466", ctx)[1]
                for key, ctx in non_sample_contexts.items()
            }
            self.assertEqual(set(non_sample_results.values()), {"11in"})

if __name__ == "__main__":
    unittest.main()
