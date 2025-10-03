import unittest
from order_gui import build_queue_url

class QueueURLTest(unittest.TestCase):
    def test_relative_url_resolution(self):
        url = build_queue_url('https://example.com/index.php', '/orders/queue.php')
        self.assertEqual(url, 'https://example.com/orders/queue.php')

if __name__ == '__main__':
    unittest.main()
