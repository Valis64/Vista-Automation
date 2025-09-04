import unittest
import tempfile
import os
from order_gui import find_art_file

class FindArtFileTest(unittest.TestCase):
    def test_name_hint_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            art_dir = os.path.join(tmp, "art")
            os.makedirs(art_dir)
            fname = "LB3186_#1.ai"
            open(os.path.join(art_dir, fname), "w").close()
            path = find_art_file(art_dir, "", name_hint="LB3186_#1")
            self.assertEqual(path, os.path.join(art_dir, fname))

if __name__ == "__main__":
    unittest.main()
