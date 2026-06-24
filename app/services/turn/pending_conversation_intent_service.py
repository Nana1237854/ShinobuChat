"""Pending conversation intent service (v1: in-memory TTL).

Tracks conversation-level intents between turns so that short replies
("yes", "ok", "listen") can be resolved against the previous turn's
pending intent.

v1 limitation: single-process, lost on restart, no multi-worker sharing.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

DEFAULT_TTL_SECONDS = 300


class PendingConversationIntentService:
    """In-memory store for conversation-level pending intents with TTL."""

    def __init__(self):
        self._store: dict[str, tuple[dict[str, Any], float]] = {}

    @staticmethod
    def _key(user_id: UUID, conversation_id: UUID) -> str:
        return f"{user_id}:{conversation_id}"

    def get_active(self, user_id: UUID, conversation_id: UUID) -> dict[str, Any] | None:
        """Return the active pending intent, or None if expired / missing."""
        key = self._key(user_id, conversation_id)
        entry = self._store.get(key)
        if entry is None:
            return None
        intent, expires_at = entry
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return intent

    def save(
        self,
        user_id: UUID,
        conversation_id: UUID,
        intent: dict[str, Any],
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        """Save a pending intent with TTL."""
        key = self._key(user_id, conversation_id)
        self._store[key] = (intent, time.monotonic() + ttl_seconds)

    def consume(self, user_id: UUID, conversation_id: UUID) -> dict[str, Any] | None:
        """Return and remove the active pending intent."""
        key = self._key(user_id, conversation_id)
        entry = self._store.pop(key, None)
        if entry is None:
            return None
        intent, expires_at = entry
        if time.monotonic() > expires_at:
            return None
        return intent

    def clear(self, user_id: UUID, conversation_id: UUID) -> None:
        """Remove any pending intent without returning it."""
        key = self._key(user_id, conversation_id)
        self._store.pop(key, None)
