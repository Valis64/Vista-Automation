import unittest
from utils.common import is_coffee_sleeve

class CoffeeSleeveTest(unittest.TestCase):
    def test_is_coffee(self):
        self.assertTrue(is_coffee_sleeve("CD0434"))
        self.assertFalse(is_coffee_sleeve("cd9999"))
        self.assertFalse(is_coffee_sleeve("RT3466"))

if __name__ == "__main__":
    unittest.main()
