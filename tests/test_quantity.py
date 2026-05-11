import unittest
from order_gui import get_item_quantity, is_quantity_one_pair


class QuantityParseTest(unittest.TestCase):
    def test_info_field(self):
        item = {"info": "Quantity: 250"}
        self.assertEqual(get_item_quantity(item), 250)

    def test_info_field_quantity_one(self):
        item = {"info": "Quantity: 1"}
        self.assertEqual(get_item_quantity(item), 1)

    def test_glue_brackets(self):
        item = {"gluetab": "34780 - vista - #1 - [11]"}
        self.assertEqual(get_item_quantity(item), 11)

    def test_glue_plain(self):
        item = {"gluetab": "34780 - vista - #1 - 111"}
        self.assertEqual(get_item_quantity(item), 111)

    def test_missing(self):
        item = {"gluetab": "no qty"}
        self.assertEqual(get_item_quantity(item), 0)

    def test_quantity_one_pair_helper(self):
        self.assertTrue(is_quantity_one_pair({"info": "Quantity: 1"}))
        self.assertFalse(
            is_quantity_one_pair({"gluetab": "34780 - vista - #1 - [11]"})
        )


if __name__ == "__main__":
    unittest.main()
