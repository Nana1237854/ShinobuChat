"""Embedding service with pluggable providers.

Supports:
- none: returns None (no-op)
- google: Google Gemini Embedding via GoogleEmbeddingProvider
- local: sklearn TF-IDF fallback

Provider selection is per-user via ConfigService.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.core.config import settings
from app.services.http_client import UrllibHttpClient

logger = logging.getLogger("shinobu.embedding")


class EmbeddingService:
    """Pluggable embedding service for memory / diary semantic retrieval.

    Provider selection resolved per-user via ConfigService:
    - "none" → returns None
    - "google" → uses GoogleEmbeddingProvider
    - "local" or unset → local TF-IDF fallback
    """

    def __init__(
        self,
        http_client: UrllibHttpClient | None = None,
        config_service=None,
    ):
        self.http_client = http_client or UrllibHttpClient()
        self.config_service = config_service
        self._local_vectorizer = None
        self._google_providers: dict[str, object] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """Legacy embed (no user context). Respects settings.memory_embedding_*
        for backward compatibility with MemoryService and existing tests."""
        content = text.strip()
        if not content:
            return []

        # Only use remote if memory-specific embedding URL is configured (legacy path)
        if settings.memory_embedding_base_url and settings.memory_embedding_api_key:
            return self._embed_remote_legacy(
                content, settings.memory_embedding_base_url, settings.memory_embedding_api_key
            )

        return self._embed_local(content)

    def embed_query(self, user_id: UUID, text: str) -> list[float] | None:
        """Embed a query text using the user's configured provider.

        Returns None when provider is 'none' or unavailable.
        """
        return self._embed_with_config(user_id, text, task_type="retrieval_query")

    def embed_text(self, user_id: UUID, text: str) -> list[float] | None:
        """Embed a document text using the user's configured provider.

        Returns None when provider is 'none' or unavailable.
        """
        return self._embed_with_config(user_id, text, task_type="retrieval_document")

    def embed_documents(
        self, user_id: UUID, texts: list[str]
    ) -> list[list[float] | None]:
        """Embed multiple documents; returns one vector (or None) per text."""
        return [self.embed_text(user_id, t) for t in texts]

    # ------------------------------------------------------------------
    # Legacy remote embedding (backward-compatible, uses global settings)
    # ------------------------------------------------------------------

    def _embed_remote_legacy(self, content: str, base_url: str, api_key: str) -> list[float]:
        """Legacy OpenAI-compatible remote embedding (pre-ConfigService path)."""
        from app.core.exceptions import UpstreamServiceError

        body = {"model": settings.memory_embedding_model, "input": content}
        try:
            response_data = self.http_client.request_json(
                f"{base_url.rstrip('/')}/embeddings",
                method="POST",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                body=body,
                timeout=settings.ai_request_timeout_seconds,
            )
        except Exception as exc:
            raise UpstreamServiceError(f"Embedding API request failed: {exc}") from exc
        try:
            embedding = response_data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise UpstreamServiceError("Embedding API returned an invalid response") from exc
        vector = [float(item) for item in embedding]
        if len(vector) != settings.memory_embedding_dimensions:
            raise UpstreamServiceError(
                f"Embedding vector dimension mismatch: expected {settings.memory_embedding_dimensions}, "
                f"got {len(vector)}"
            )
        return vector

    # ------------------------------------------------------------------
    # Provider resolution
    # ------------------------------------------------------------------

    def _resolve_provider(self, user_id: UUID) -> str:
        """Return the effective embedding provider for *user_id*."""
        if self.config_service:
            try:
                return self.config_service.get_effective_value(user_id, "embedding_provider") or "none"
            except Exception:
                pass
        return "none"

    def _embed_with_config(
        self, user_id: UUID, text: str, *, task_type: str = "retrieval_query"
    ) -> list[float] | None:
        content = text.strip()
        if not content:
            return None

        provider = self._resolve_provider(user_id)

        if provider == "none":
            return None

        if provider == "google":
            return self._embed_google(user_id, content, task_type=task_type)

        # local or unknown → local TF-IDF
        return self._embed_local(content)

    def _embed_google(
        self, user_id: UUID, content: str, *, task_type: str = "retrieval_query"
    ) -> list[float] | None:
        """Use Google Gemini Embedding via a cached provider instance."""
        if not self.config_service:
            logger.warning("EmbeddingService: no config_service available for Google provider")
            return None

        try:
            api_key = self.config_service.get_effective_value(user_id, "google_embedding_api_key")
            if not api_key or not api_key.strip():
                logger.debug("EmbeddingService: google_embedding_api_key not configured for user %s", user_id)
                return None

            model = self.config_service.get_effective_value(user_id, "embedding_model") or "gemini-embedding-001"
            base_url = self.config_service.get_effective_value(user_id, "google_embedding_base_url") or ""
            timeout = self.config_service.get_effective_value(user_id, "embedding_timeout_seconds") or 30
        except Exception:
            logger.warning("EmbeddingService: failed to read Google config for user %s", user_id, exc_info=True)
            return None

        # Cache provider per unique (api_key, model, base_url) key
        cache_key = f"{api_key[:8]}:{model}:{base_url}"
        if cache_key not in self._google_providers:
            from app.services.embedding_providers.google_embedding_provider import (
                GoogleEmbeddingProvider,
            )
            self._google_providers[cache_key] = GoogleEmbeddingProvider(
                api_key=api_key,
                model=model,
                base_url=base_url or None,
                timeout=int(timeout),
                http_client=self.http_client,
            )

        provider = self._google_providers[cache_key]
        try:
            return provider.embed(content, task_type=task_type)
        except Exception:
            logger.warning("Google Embedding failed for query", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Local fallback
    # ------------------------------------------------------------------

    def _embed_local(self, content: str) -> list[float]:
        if self._local_vectorizer is None:
            self._local_vectorizer = _create_vectorizer()
        vec = self._local_vectorizer([content])
        return [float(v) for v in vec[0]]


def _create_vectorizer():
    """Create a lightweight sklearn TfidfVectorizer with character n-grams."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np
    except ImportError:
        # sklearn not available — return a zero vector
        def _zeros(_texts):
            return [[0.0] * settings.memory_embedding_dimensions]
        return _zeros

    dims = settings.memory_embedding_dimensions
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        max_features=dims,
        dtype=np.float32,
    )

    seed = [
        "你好我是Shinobu你的AI伙伴",
        "今天天气真好阳光明媚",
        "帮我查一下纽约的天气",
        "我喜欢抹茶和夜跑",
        "用户偏好设置和记忆",
        "the quick brown fox jumps over the lazy dog",
        "machine learning natural language processing",
        "hello world how are you doing today",
    ]
    vectorizer.fit(seed)

    def encode(texts):
        X = vectorizer.transform(texts)
        from sklearn.preprocessing import normalize
        X = normalize(X, norm="l2")
        result = np.zeros((len(texts), dims), dtype=np.float32)
        n_features = min(X.shape[1], dims)
        if hasattr(X, 'toarray'):
            result[:, :n_features] = X[:, :n_features].toarray()
        else:
            result[:, :n_features] = X[:, :n_features]
        return result.tolist()

    return encode
