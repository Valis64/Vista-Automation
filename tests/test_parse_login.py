import unittest
from order_gui import parse_login_form

HTML = """
<form method="post" action="https://example.com/index.php">
  <input name="email" type="text" value="">
  <input name="password" type="password" value="">
  <input type="hidden" name="action" value="signin">
</form>
"""

class LoginFormTest(unittest.TestCase):
    def test_form_parsing(self):
        url, method, data = parse_login_form(HTML, "https://example.com/index.php", "u", "p")
        self.assertEqual(url, "https://example.com/index.php")
        self.assertEqual(method, "post")
        self.assertEqual(data["email"], "u")
        self.assertEqual(data["password"], "p")
        self.assertEqual(data["action"], "signin")

if __name__ == "__main__":
    unittest.main()
