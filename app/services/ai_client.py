from __future__ import annotations

import json
from typing import Iterator

from app.core.config import settings
from app.core.exceptions import ConfigurationError, UpstreamServiceError
from app.services.http_client import HttpClientError, UrllibHttpClient


class AIClient:
    def __init__(self, http_client: UrllibHttpClient | None = None):
        self.http_client = http_client or UrllibHttpClient()

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        body = self._build_body(messages, temperature=0.7, stream=True, max_tokens=max_tokens)
        try:
            for line in self.http_client.stream_lines(
                self._chat_completions_endpoint(),
                method="POST",
                headers=self._headers(),
                body=body,
                timeout=settings.ai_request_timeout_seconds,
            ):
                token = self._parse_stream_token(line)
                if token:
                    yield token
        except HttpClientError as exc:
            raise UpstreamServiceError(f"AI API request failed: {exc}") from exc

    def complete_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        body = self._build_body(messages, temperature=0.4, stream=False, max_tokens=max_tokens)
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        try:
            response_data = self.http_client.request_json(
                self._chat_completions_endpoint(),
                method="POST",
                headers=self._headers(),
                body=body,
                timeout=settings.ai_request_timeout_seconds,
            )
        except HttpClientError as exc:
            raise UpstreamServiceError(f"AI API request failed: {exc}") from exc

        try:
            return response_data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise UpstreamServiceError("AI API returned an invalid completion response") from exc

    def _build_body(
        self,
        messages: list[dict],
        *,
        temperature: float,
        stream: bool,
        max_tokens: int | None,
    ) -> dict:
        self._ensure_configured()
        body: dict = {
            "model": settings.ai_model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        return body

    def _ensure_configured(self) -> None:
        if not settings.ai_api_key or settings.ai_api_key == "your-api-key":
            raise ConfigurationError("AI API key is not configured")

    def _chat_completions_endpoint(self) -> str:
        return f"{settings.ai_base_url.rstrip('/')}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        }

    def _parse_stream_token(self, line: bytes) -> str:
        if not line or line == b"data: [DONE]" or not line.startswith(b"data: "):
            return ""
        try:
            chunk_data = json.loads(line[6:])
            delta = chunk_data.get("choices", [{}])[0].get("delta", {})
            return delta.get("content", "")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            return ""
