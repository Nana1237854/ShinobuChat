import json
import unittest
from unittest.mock import MagicMock

from fastapi import status

from app.api.error_handlers import app_error_handler
from app.core.exceptions import ForbiddenError, PayloadTooLargeError


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


if __name__ == "__main__":
    unittest.main()
