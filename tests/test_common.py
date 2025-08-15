import unittest
from utils.common import get_laminate_color, LAM_COLORS


class CommonUtilsTest(unittest.TestCase):
    def test_get_laminate_color(self):
        self.assertEqual(get_laminate_color("Gloss"), LAM_COLORS["gloss"])
        self.assertEqual(get_laminate_color("unknown"), "#000000")


if __name__ == "__main__":
    unittest.main()
