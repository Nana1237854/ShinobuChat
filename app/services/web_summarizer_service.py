"""Web summarizer service — LLM-based web page summarization."""

from __future__ import annotations

import json
import logging
from uuid import UUID

from app.core.config import settings
from app.services.ai_client import AIClient
from app.services.http_client import UrllibHttpClient
from app.services.web_reader_service import WebReaderService

logger = logging.getLogger(__name__)


class WebSummarizerService:
    """Read a web page and summarize it using the configured LLM."""

    def __init__(
        self,
        ai_client: AIClient | None = None,
        http_client: UrllibHttpClient | None = None,
    ) -> None:
        self._ai = ai_client
        self._reader = WebReaderService(http_client)

    def summarize(
        self,
        url: str,
        user_id: UUID | None = None,
        question: str = "",
        max_chars: int = 10000,
        runtime_config: dict | None = None,
    ) -> dict:
        """Read *url* and return an LLM-generated summary.

        *runtime_config* is forwarded to AIClient.stream_chat() so that
        per-user AI keys/models are used instead of global settings.

        Returns:
          dict with: status, summary, key_points, source_url, message
        """
        reader_result = self._reader.read(url, user_id=user_id, max_chars=max_chars)
        if reader_result["status"] != "ok":
            return {
                "status": "error",
                "summary": "",
                "key_points": [],
                "source_url": url,
                "message": reader_result.get("message", "Failed to read the page."),
            }

        content = reader_result["content"]
        title = reader_result["title"]

        if not content.strip():
            return {
                "status": "error",
                "summary": "",
                "key_points": [],
                "source_url": url,
                "message": "The page has no readable text content.",
            }

        if self._ai is None:
            return {
                "status": "error",
                "summary": "",
                "key_points": [],
                "source_url": url,
                "message": "AI client is not configured. Please set an API key in settings.",
            }

        prompt = _build_summary_prompt(title, url, content, question)

        try:
            full_response = ""
            for chunk in self._ai.stream_chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                runtime_config=runtime_config,
            ):
                full_response += chunk
        except Exception as exc:
            logger.warning("Summarization failed: %s", exc)
            return {
                "status": "error",
                "summary": "",
                "key_points": [],
                "source_url": url,
                "message": f"LLM summarization failed: {exc}",
            }

        parsed = _parse_summary_response(full_response)
        parsed["source_url"] = url
        parsed["status"] = "ok"
        return parsed


def _build_summary_prompt(title: str, url: str, content: str, question: str) -> str:
    q = question or "Summarize the main content of this page."
    return (
        f"You are a helpful assistant. Read the following web page content and answer the question.\n\n"
        f"Page title: {title}\n"
        f"Page URL: {url}\n\n"
        f"--- PAGE CONTENT ---\n{content[:6000]}\n--- END ---\n\n"
        f"Question: {q}\n\n"
        f"Respond in JSON format:\n"
        f'{{"summary": "A concise summary in 2-4 sentences", '
        f'"key_points": ["Point 1", "Point 2", "Point 3"]}}'
    )


def _parse_summary_response(text: str) -> dict:
    try:
        data = json.loads(text)
        return {
            "summary": str(data.get("summary", "")),
            "key_points": [str(p) for p in data.get("key_points", [])],
            "source_url": "",
            "message": "",
        }
    except (json.JSONDecodeError, TypeError):
        return {
            "summary": text.strip(),
            "key_points": [],
            "source_url": "",
            "message": "",
        }
