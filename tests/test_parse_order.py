import unittest
from order_gui import parse_order

SAMPLE_HTML = '''
<div class="order-items">
  <div class="item">
    <span class="qty">11</span>
    <span class="template">LB2022</span>
    <span class="art-full">LB2022G - M7H80949EF</span>
  </div>
  <div class="item">
    <span class="qty">11</span>
    <span class="template">RT3466</span>
    <span class="art-full">RT3466G - ME716H2DTG</span>
  </div>
</div>
'''

class ParseOrderTest(unittest.TestCase):
    def test_pairs_extracted(self):
        data = parse_order(SAMPLE_HTML)
        self.assertIn("pairs", data)
        self.assertEqual(len(data["pairs"]), 2)
        self.assertEqual(data["pairs"][0]["template"], "LB2022")
        self.assertEqual(data["pairs"][0]["art_id"], "M7H80949EF")
        self.assertEqual(data["pairs"][1]["template"], "RT3466")
        self.assertEqual(data["pairs"][1]["art_id"], "ME716H2DTG")

    def test_pairs_from_table(self):
        html = '''<tbody id="unordered_items_tbody">\n<tr><td><table class="table table-inside"><tbody><tr><td><strong>250</strong></td><td><strong>RT3466</strong></td><td><strong>RT3466G - MBG19D57CB</strong></td></tr><tr><td></td><td></td><td class="text-left"><span class="fl_name">34671_RT3466G_MBG19D57CB_#1</span></td></tr></tbody></table></td></tr><tr><td><table class="table table-inside"><tbody><tr><td><strong>2500</strong></td><td><strong>RT3466</strong></td><td><strong>RT3466G - M955D3G6E4</strong></td></tr><tr><td></td><td></td><td class="text-left"><span class="fl_name">34671_RT3466G_M955D3G6E4_#2</span></td></tr></tbody></table></td></tr></tbody>'''
        data = parse_order(html)
        self.assertEqual(len(data["pairs"]), 2)
        self.assertEqual(data["pairs"][0]["template"], "RT3466")
        self.assertEqual(data["pairs"][0]["art_id"], "MBG19D57CB")
        self.assertEqual(data["pairs"][1]["template"], "RT3466")
        self.assertEqual(data["pairs"][1]["art_id"], "M955D3G6E4")

    def test_three_part_art_full(self):
        html = '''
        <div class="order-items">
          <div class="item">
            <span class="qty">1</span>
            <span class="template">RTVista06G</span>
            <span class="art-full">RTVista06G - MED544GD9G - FZ2BBDAH99</span>
          </div>
        </div>
        '''
        data = parse_order(html)
        self.assertEqual(len(data["pairs"]), 1)
        self.assertEqual(data["pairs"][0]["template"], "RTVista06G")
        self.assertEqual(data["pairs"][0]["art_id"], "MED544GD9G")

    def test_order_info_extracted(self):
        html = """
        <div id="details">
            <table><tbody>
            <tr><td><strong>Order ID: </strong>12345</td></tr>
            <tr><td><strong>Created By: </strong>Justin Fish</td></tr>
            <tr><td><strong>Ordered By: </strong>Sara Parisi</td></tr>
            <tr><td><strong>Company: </strong>Vista Print</td></tr>
            </tbody></table>
        </div>
        """
        data = parse_order(html)
        info = data.get("order_info", {})
        self.assertEqual(info.get("order_id"), "12345")
        self.assertEqual(info.get("created_by"), "Justin Fish")
        self.assertEqual(info.get("ordered_by"), "Sara Parisi")
        self.assertEqual(info.get("company"), "Vista Print")

    def test_order_info_complex(self):
        html = """
        <div id="details">
            <table><tbody>
            <tr><td><strong>Order ID: </strong>34671</td></tr>
            <tr><td><strong>Created By: </strong>Justin Fish (<a class="switch-rep" href="admin/switch-rep.php?id=34671">switch</a>)</td></tr>
            <tr><td><strong>Ordered By: </strong>Sara Parisi (#<a target="_blank" href="admin/members-form.php?id=5733">5733</a>)</td></tr>
            <tr><td><strong>Company: </strong>Vista Print<br></td></tr>
            </tbody></table>
        </div>
        """
        data = parse_order(html)
        info = data.get("order_info", {})
        self.assertEqual(info.get("order_id"), "34671")
        self.assertEqual(info.get("created_by"), "Justin Fish")
        self.assertEqual(info.get("ordered_by"), "Sara Parisi")
        self.assertEqual(info.get("company"), "Vista Print")

if __name__ == "__main__":
    unittest.main()
