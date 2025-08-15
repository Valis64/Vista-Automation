import unittest
from order_gui import parse_queue

HTML = """
<table>
  <tr>
    <th>WF</th><th>ID</th><th>SR</th><th>Company Name</th>
  </tr>
  <tr>
    <td>YBS</td><td>12345</td><td></td><td>Vista Print</td>
  </tr>
  <tr>
    <td>YBS</td><td>54321</td><td></td><td>Other Co</td>
  </tr>
  <tr>
    <td>YBS</td><td>22222</td><td></td><td>Vista Boxes</td>
  </tr>
</table>
"""

class QueueParseTest(unittest.TestCase):
    def test_vista_orders_extracted(self):
        ids = parse_queue(HTML)
        self.assertEqual(ids, ["12345", "22222"])

if __name__ == "__main__":
    unittest.main()
