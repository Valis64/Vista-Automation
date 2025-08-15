import unittest
from utils.common import is_pb001

class PB001Test(unittest.TestCase):
    def test_is_pb001(self):
        self.assertTrue(is_pb001("PB001"))
        self.assertFalse(is_pb001("pb002"))
        self.assertFalse(is_pb001("RT3466"))

if __name__ == "__main__":
    unittest.main()
