import unittest

from app.core.exceptions import BadRequestError
from app.core.url_validation import validate_url_safe


class UrlValidationTests(unittest.TestCase):
    def test_allows_public_https_url(self):
        validate_url_safe("https://example.com/skill.md")

    def test_rejects_file_scheme(self):
        with self.assertRaises(BadRequestError) as ctx:
            validate_url_safe("file:///etc/passwd")
        self.assertIn("http or https", str(ctx.exception.detail))

    def test_rejects_missing_scheme(self):
        with self.assertRaises(BadRequestError):
            validate_url_safe("example.com/skill.md")

    def test_rejects_no_hostname(self):
        with self.assertRaises(BadRequestError):
            validate_url_safe("http:///path")

    def test_rejects_localhost_hostname(self):
        with self.assertRaises(BadRequestError) as ctx:
            validate_url_safe("http://localhost:8080/admin")
        self.assertIn("disallowed host", str(ctx.exception.detail))

    def test_rejects_localhost_ipv4(self):
        with self.assertRaises(BadRequestError) as ctx:
            validate_url_safe("http://127.0.0.1:8080/admin")
        self.assertIn("private or reserved", str(ctx.exception.detail).lower())

    def test_rejects_localhost_ipv6(self):
        with self.assertRaises(BadRequestError) as ctx:
            validate_url_safe("http://[::1]:8080/admin")
        self.assertIn("private or reserved", str(ctx.exception.detail).lower())

    def test_rejects_private_ipv4_class_a(self):
        with self.assertRaises(BadRequestError):
            validate_url_safe("http://10.0.0.1/admin")

    def test_rejects_private_ipv4_class_b(self):
        with self.assertRaises(BadRequestError):
            validate_url_safe("http://172.16.0.1/admin")

    def test_rejects_private_ipv4_class_c(self):
        with self.assertRaises(BadRequestError):
            validate_url_safe("http://192.168.1.1/admin")

    def test_rejects_link_local(self):
        with self.assertRaises(BadRequestError):
            validate_url_safe("http://169.254.1.1/admin")

    def test_rejects_zero_ip(self):
        with self.assertRaises(BadRequestError):
            validate_url_safe("http://0.0.0.0:8080/admin")


if __name__ == "__main__":
    unittest.main()
