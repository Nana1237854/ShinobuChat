import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict

from app.core.exceptions import TooManyRequestsError


class RateLimiterBackend(ABC):
    @abstractmethod
    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool: ...


class MemoryRateLimiterBackend(RateLimiterBackend):
    def __init__(self) -> None:
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _evict(self, key: str, window_seconds: float) -> None:
        now = time.monotonic()
        timestamps = self._store[key]
        cutoff = now - window_seconds
        while timestamps and timestamps[0] <= cutoff:
            timestamps.pop(0)

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        with self._lock:
            self._evict(key, window_seconds)
            timestamps = self._store[key]
            if len(timestamps) < limit:
                timestamps.append(time.monotonic())
                return True
            return False

    def oldest_timestamp(self, key: str) -> float | None:
        with self._lock:
            ts = self._store.get(key)
            return ts[0] if ts else None


class RateLimiter:
    def __init__(self, backend: RateLimiterBackend | None = None) -> None:
        self._backend = backend or MemoryRateLimiterBackend()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        if self._backend.is_allowed(key, limit, window_seconds):
            return
        now = time.monotonic()
        oldest = self._backend.oldest_timestamp(key)
        if oldest is not None:
            retry_after = max(1, int(window_seconds - (now - oldest)))
        else:
            retry_after = window_seconds
        raise TooManyRequestsError(
            f"Rate limit exceeded for {key}. Try again in {retry_after} seconds.",
            retry_after=retry_after,
        )
