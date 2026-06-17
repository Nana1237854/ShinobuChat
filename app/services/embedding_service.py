from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import ConfigurationError, UpstreamServiceError
from app.services.http_client import HttpClientError, UrllibHttpClient


class EmbeddingService:
    def __init__(self, http_client: UrllibHttpClient | None = None):
        self.http_client = http_client or UrllibHttpClient()
        self._local_vectorizer = None

    def embed(self, text: str) -> list[float]:
        content = text.strip()
        if not content:
            return []

        # Only use remote if memory-specific embedding URL is configured
        if settings.memory_embedding_base_url and settings.memory_embedding_api_key:
            return self._embed_remote(
                content, settings.memory_embedding_base_url, settings.memory_embedding_api_key
            )

        return self._embed_local(content)

    def _embed_remote(self, content: str, base_url: str, api_key: str) -> list[float]:
        body = {"model": settings.memory_embedding_model, "input": content}
        try:
            response_data = self.http_client.request_json(
                f"{base_url.rstrip('/')}/embeddings",
                method="POST",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                body=body,
                timeout=settings.ai_request_timeout_seconds,
            )
        except HttpClientError as exc:
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

    def _embed_local(self, content: str) -> list[float]:
        if self._local_vectorizer is None:
            self._local_vectorizer = _create_vectorizer()
        vec = self._local_vectorizer([content])
        return [float(v) for v in vec[0]]


def _create_vectorizer():
    """Create a lightweight sklearn TfidfVectorizer with character n-grams.
    Returns a callable that maps text -> fixed-size float vectors."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    import numpy as np

    dims = settings.memory_embedding_dimensions
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        max_features=dims,
        dtype=np.float32,
    )

    # Fit on some Chinese + English seed texts so the vocabulary is non-empty
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
        # Normalize to unit vector
        from sklearn.preprocessing import normalize
        X = normalize(X, norm="l2")
        # Pad/truncate to target dimensions
        result = np.zeros((len(texts), dims), dtype=np.float32)
        n_features = min(X.shape[1], dims)
        result[:, :n_features] = X[:, :n_features].toarray() if hasattr(X, 'toarray') else X[:, :n_features]
        return result.tolist()

    return encode
