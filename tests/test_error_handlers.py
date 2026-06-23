import json
import unittest
from unittest.mock import MagicMock

from fastapi import status

from app.api.error_handlers import app_error_handler
from app.core.exceptions import ForbiddenError, PayloadTooLargeError, TooManyRequestsError


class ErrorHandlerTests(unittest.TestCase):
    def setUp(self):
        self.mock_request = MagicMock()

    def test_forbidden_error_maps_to_403(self):
        import asyncio

        exc = ForbiddenError("Access denied")
        resp = asyncio.run(app_error_handler(self.mock_request, exc))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.body, b'{"detail":"Access denied"}')

    def test_payload_too_large_error_maps_to_413(self):
        import asyncio

        exc = PayloadTooLargeError(
            "Image too large: 999999 bytes exceeds 100000 bytes limit"
        )
        resp = asyncio.run(app_error_handler(self.mock_request, exc))
        self.assertEqual(resp.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        data = json.loads(resp.body.decode())
        self.assertEqual(data["detail"], exc.detail)

    def test_too_many_requests_maps_to_429_with_retry_after(self):
        import asyncio

        exc = TooManyRequestsError("Rate limit exceeded for test", retry_after=42)
        resp = asyncio.run(app_error_handler(self.mock_request, exc))
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        data = json.loads(resp.body.decode())
        self.assertEqual(data["detail"], exc.detail)
        self.assertEqual(resp.headers.get("Retry-After"), "42")

    def test_too_many_requests_without_retry_after_has_no_header(self):
        import asyncio

        exc = TooManyRequestsError("Rate limited")
        resp = asyncio.run(app_error_handler(self.mock_request, exc))
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertNotIn("Retry-After", resp.headers)


if __name__ == "__main__":
    unittest.main()
