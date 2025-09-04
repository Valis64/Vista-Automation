import unittest
import tempfile
import os

from order_gui import move_art_to_folder


class MoveArtTest(unittest.TestCase):
    def test_move_art_to_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            order_dir = os.path.join(tmp, "12345")
            os.makedirs(order_dir)
            art1 = os.path.join(order_dir, "sample.ai")
            art2 = os.path.join(order_dir, "extra.pdf")
            open(art1, "w").close()
            open(art2, "w").close()

            moved = move_art_to_folder(order_dir)

            art_dir = os.path.join(order_dir, "art")
            self.assertEqual(moved, 2)
            self.assertTrue(os.path.isdir(art_dir))
            self.assertTrue(os.path.isfile(os.path.join(art_dir, "sample.ai")))
            self.assertTrue(os.path.isfile(os.path.join(art_dir, "extra.pdf")))


if __name__ == "__main__":
    unittest.main()

