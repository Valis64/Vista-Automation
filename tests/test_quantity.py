import unittest
from order_gui import get_item_quantity

class QuantityParseTest(unittest.TestCase):
    def test_info_field(self):
        item = {"info": "Quantity: 250"}
        self.assertEqual(get_item_quantity(item), 250)

    def test_glue_brackets(self):
        item = {"gluetab": "34780 - vista - #1 - [11]"}
        self.assertEqual(get_item_quantity(item), 11)

    def test_glue_plain(self):
        item = {"gluetab": "34780 - vista - #1 - 111"}
        self.assertEqual(get_item_quantity(item), 111)

    def test_missing(self):
        item = {"gluetab": "no qty"}
        self.assertEqual(get_item_quantity(item), 0)

if __name__ == "__main__":
    unittest.main()
