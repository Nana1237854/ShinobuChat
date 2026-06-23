"""Google Gemini Embedding provider.

Calls the Google Generative Language API to produce embedding vectors.
Designed to be used through EmbeddingService — never called directly by
ActionReplyGenerationService or chat code.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.http_client import HttpClientError, UrllibHttpClient

logger = logging.getLogger("shinobu.embedding.google")

_DEFAULT_GOOGLE_EMBEDDING_URL = "https://generativelanguage.googleapis.com/v1beta"


class GoogleEmbeddingProvider:
    """Produce embeddings via Google Gemini Embedding API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-embedding-001",
        base_url: str | None = None,
        timeout: int = 30,
        http_client: UrllibHttpClient | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "").strip().rstrip("/") or _DEFAULT_GOOGLE_EMBEDDING_URL
        self.timeout = timeout
        self.http_client = http_client or UrllibHttpClient()

    def embed(self, text: str, *, task_type: str = "retrieval_query") -> list[float] | None:
        """Return an embedding vector for *text*, or None on failure."""
        content = text.strip()
        if not content:
            return None

        url = f"{self.base_url}/models/{self.model}:batchEmbedContents"
        body: dict[str, Any] = {
            "requests": [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": content}]},
                    "taskType": task_type,
                }
            ]
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        try:
            response = self.http_client.request_json(
                url,
                method="POST",
                headers=headers,
                body=body,
                timeout=self.timeout,
            )
        except HttpClientError as exc:
            logger.warning("Google Embedding API request failed: %s", exc)
            return None
        except Exception:
            logger.warning("Google Embedding API unexpected error", exc_info=True)
            return None

        try:
            embeddings = response.get("embeddings")
            if not embeddings or not isinstance(embeddings, list):
                logger.warning("Google Embedding API returned empty embeddings")
                return None
            values = embeddings[0].get("values")
            if not values:
                return None
            return [float(v) for v in values]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("Google Embedding API returned invalid response: %s", exc)
            return None
