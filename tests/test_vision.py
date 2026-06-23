import io
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from app.core.exceptions import BadRequestError, ConfigurationError, UpstreamServiceError
from app.core.image_validation import validate_image_bytes
from app.services.vision_client import (
    OCRVisionClient,
    OpenAIVisionClient,
    VisionAnalyzeResult,
    _extract_json_object,
)


def _make_jpeg_bytes(width=100, height=100):
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=(128, 128, 128))
    img.save(buf, format="JPEG")
    return buf.getvalue()


class ImageValidationTests(unittest.TestCase):
    def test_empty_file_raises(self):
        with self.assertRaises(BadRequestError) as ctx:
            validate_image_bytes(b"", max_bytes=1024, max_side=100, max_pixels=10000)
        self.assertIn("empty", str(ctx.exception.detail))

    def test_non_image_raises(self):
        with self.assertRaises(BadRequestError) as ctx:
            validate_image_bytes(b"not an image at all", max_bytes=1024, max_side=100, max_pixels=10000)
        self.assertIn("Unrecognized", str(ctx.exception.detail))

    def test_oversized_bytes_raises(self):
        data = _make_jpeg_bytes(10, 10)
        with self.assertRaises(BadRequestError) as ctx:
            validate_image_bytes(data, max_bytes=len(data) - 1, max_side=100, max_pixels=10000)
        self.assertIn("too large", str(ctx.exception.detail))

    def test_oversized_dimensions_raises(self):
        data = _make_jpeg_bytes(200, 200)
        with self.assertRaises(BadRequestError) as ctx:
            validate_image_bytes(data, max_bytes=1024 * 1024, max_side=100, max_pixels=10000)
        self.assertIn("dimensions", str(ctx.exception.detail))

    def test_oversized_pixels_raises(self):
        data = _make_jpeg_bytes(100, 200)
        with self.assertRaises(BadRequestError) as ctx:
            validate_image_bytes(data, max_bytes=1024 * 1024, max_side=500, max_pixels=19999)
        self.assertIn("pixel", str(ctx.exception.detail))

    def test_valid_image_returns_bytes_and_mime(self):
        data = _make_jpeg_bytes(50, 50)
        validated, mime = validate_image_bytes(data, max_bytes=1024 * 1024, max_side=100, max_pixels=10000)
        self.assertIsInstance(validated, bytes)
        self.assertTrue(len(validated) > 0)
        self.assertEqual(mime, "image/jpeg")


class ExtractJsonObjectTests(unittest.TestCase):
    def test_plain_json(self):
        result = _extract_json_object('{"summary":"test","objects":["a"],"confidence":0.8}')
        self.assertEqual(result["summary"], "test")
        self.assertEqual(result["objects"], ["a"])

    def test_fenced_json(self):
        result = _extract_json_object('```json\n{"summary":"fenced","objects":[],"confidence":0.5}\n```')
        self.assertEqual(result["summary"], "fenced")

    def test_json_with_leading_text(self):
        result = _extract_json_object('Here is my analysis:\n{"summary":"text","objects":["b"],"confidence":0.9}\nHope this helps!')
        self.assertEqual(result["summary"], "text")

    def test_non_json_fallback(self):
        result = _extract_json_object("This is just plain text, no JSON at all.")
        self.assertIn("summary", result)
        self.assertIn("This is just plain text", result["summary"])
        self.assertEqual(result["confidence"], 0.3)

    def test_empty_text(self):
        result = _extract_json_object("")
        self.assertIn("summary", result)


class OpenAIVisionClientTests(unittest.TestCase):
    def setUp(self):
        self.client = OpenAIVisionClient()

    def test_no_api_key_raises(self):
        with patch("app.services.vision_client.settings.ai_api_key", ""):
            with self.assertRaises(ConfigurationError) as ctx:
                import asyncio
                asyncio.run(
                    self.client.analyze(
                        _make_jpeg_bytes(), "image/jpeg",
                        runtime_config={"ai_api_key": "", "ai_supports_image_input": True},
                    )
                )
            self.assertIn("No AI API key", str(ctx.exception.detail))

    def test_image_not_supported_raises(self):
        with self.assertRaises(ConfigurationError) as ctx:
            import asyncio
            asyncio.run(
                self.client.analyze(
                    _make_jpeg_bytes(), "image/jpeg",
                    runtime_config={
                        "ai_api_key": "sk-test",
                        "ai_supports_image_input": False,
                    },
                )
            )
        self.assertIn("does not support image", str(ctx.exception.detail))

    def test_structured_result(self):
        fake_response = {
            "choices": [{
                "message": {
                    "content": '{"summary":"A cat","objects":["cat","couch"],"scene":"living room","text_in_image":null,"suggestions":["pet the cat"],"confidence":0.95}'
                }
            }]
        }
        mock_http = MagicMock()
        mock_http.request_json.return_value = fake_response
        client = OpenAIVisionClient(mock_http)

        import asyncio
        result = asyncio.run(
            client.analyze(
                _make_jpeg_bytes(), "image/jpeg",
                runtime_config={
                    "ai_api_key": "sk-test",
                    "ai_base_url": "https://api.example.com/v1",
                    "ai_model": "gpt-4o",
                    "ai_supports_image_input": True,
                },
            )
        )
        self.assertEqual(result.summary, "A cat")
        self.assertEqual(result.objects, ["cat", "couch"])
        self.assertEqual(result.scene, "living room")
        self.assertEqual(result.provider, "openai")
        self.assertFalse(result.fallback_used)

    def test_non_json_response_fallback(self):
        fake_response = {
            "choices": [{
                "message": {
                    "content": "I see a beautiful landscape with mountains and a lake."
                }
            }]
        }
        mock_http = MagicMock()
        mock_http.request_json.return_value = fake_response
        client = OpenAIVisionClient(mock_http)

        import asyncio
        result = asyncio.run(
            client.analyze(
                _make_jpeg_bytes(), "image/jpeg",
                runtime_config={
                    "ai_api_key": "sk-test",
                    "ai_base_url": "https://api.example.com/v1",
                    "ai_model": "gpt-4o",
                    "ai_supports_image_input": True,
                },
            )
        )
        self.assertIn("mountains", result.summary)
        self.assertEqual(result.confidence, 0.3)
        self.assertEqual(result.provider, "openai")


class OCRVisionClientTests(unittest.TestCase):
    def test_returns_ocr_provider(self):
        fake_reader = MagicMock()
        fake_reader.readtext.return_value = [
            (None, "Hello", None),
            (None, "World", None),
        ]
        with patch.object(OCRVisionClient, "_ensure_reader", return_value=fake_reader):
            import asyncio
            result = asyncio.run(
                OCRVisionClient().analyze(_make_jpeg_bytes(), "image/jpeg")
            )
        self.assertEqual(result.provider, "ocr")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.detected_text, "Hello\nWorld")
        self.assertIn("已从图片中提取到文字", result.summary)


class ConfigurableVisionClientTests(unittest.TestCase):
    def test_openai_success_no_fallback(self):
        fake_response = {
            "choices": [{
                "message": {
                    "content": '{"summary":"test","objects":[],"scene":null,"text_in_image":null,"suggestions":[],"confidence":0.8}'
                }
            }]
        }
        mock_http = MagicMock()
        mock_http.request_json.return_value = fake_response
        from app.services.vision_client import ConfigurableVisionClient

        client = ConfigurableVisionClient(mock_http)
        import asyncio
        result = asyncio.run(
            client.analyze(
                _make_jpeg_bytes(), "image/jpeg",
                runtime_config={
                    "ai_api_key": "sk-test",
                    "ai_base_url": "https://api.example.com/v1",
                    "ai_model": "gpt-4o",
                    "ai_supports_image_input": True,
                },
            )
        )
        self.assertEqual(result.provider, "openai")
        self.assertFalse(result.fallback_used)

    def test_openai_fail_ocr_fallback(self):
        import asyncio
        from app.services.vision_client import ConfigurableVisionClient

        mock_http = MagicMock()
        mock_http.request_json.side_effect = UpstreamServiceError("API error")
        client = ConfigurableVisionClient(mock_http)

        fake_reader = MagicMock()
        fake_reader.readtext.return_value = [(None, "OCR text", None)]
        with patch.object(OCRVisionClient, "_ensure_reader", return_value=fake_reader):
            result = asyncio.run(
                client.analyze(
                    _make_jpeg_bytes(), "image/jpeg",
                    runtime_config={
                        "ai_api_key": "sk-test",
                        "ai_base_url": "https://api.example.com/v1",
                        "ai_model": "gpt-4o",
                        "ai_supports_image_input": True,
                    },
                )
            )
        self.assertEqual(result.provider, "ocr")
        self.assertTrue(result.fallback_used)

    def test_both_fail_raises_upstream_error(self):
        import asyncio
        from app.services.vision_client import ConfigurableVisionClient

        mock_http = MagicMock()
        mock_http.request_json.side_effect = UpstreamServiceError("API error")
        client = ConfigurableVisionClient(mock_http)

        with patch("app.services.vision_client.OCRVisionClient.analyze",
                   side_effect=ConfigurationError("OCR not available")):
            with self.assertRaises(UpstreamServiceError):
                asyncio.run(
                    client.analyze(
                        _make_jpeg_bytes(), "image/jpeg",
                        runtime_config={
                            "ai_api_key": "sk-test",
                            "ai_base_url": "https://api.example.com/v1",
                            "ai_model": "gpt-4o",
                            "ai_supports_image_input": True,
                        },
                    )
                )


class ImageUnderstandingServiceTests(unittest.TestCase):
    def test_does_not_import_memory_service(self):
        # Verify ImageUnderstandingService does not reference MemoryService
        import ast
        import inspect
        from app.services import image_understanding_service

        source = inspect.getsource(image_understanding_service)
        tree = ast.parse(source)
        memory_refs = [node for node in ast.walk(tree)
                       if isinstance(node, ast.Name) and node.id == "MemoryService"]
        self.assertEqual(len(memory_refs), 0, "ImageUnderstandingService must not reference MemoryService")

    def test_build_chat_context(self):
        from app.services.image_understanding_service import ImageUnderstandingService

        svc = ImageUnderstandingService()
        result = VisionAnalyzeResult(
            summary="A cat on a couch",
            objects=["cat", "couch"],
            scene="living room",
            detected_text=None,
            suggestions=["pet the cat"],
            confidence=0.95,
            provider="openai",
            fallback_used=False,
        )
        ctx = svc.build_chat_context(result)
        self.assertIn("A cat on a couch", ctx)
        self.assertIn("cat, couch", ctx)
        self.assertIn("openai", ctx)
