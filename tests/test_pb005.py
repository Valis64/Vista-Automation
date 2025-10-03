import unittest
from utils.common import is_pb005

class PB005Test(unittest.TestCase):
    def test_is_pb005(self):
        self.assertTrue(is_pb005('PB005'))
        self.assertFalse(is_pb005('pb001'))
        self.assertFalse(is_pb005('RT3466'))

if __name__ == '__main__':
    unittest.main()
