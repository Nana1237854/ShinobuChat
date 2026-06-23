"""Task event service — semantic emit helpers for task lifecycle events."""

from __future__ import annotations

from app.domains.tasks.task_event_store import TaskEventStore


class TaskEventService:
    def __init__(self, store: TaskEventStore):
        self.store = store

    def emit_started(self, task_id: str, user_id, message: str = "") -> None:
        self.store.emit(
            task_id, "task_started", {"message": message}, user_id=str(user_id)
        )

    def emit_progress(self, task_id: str, user_id, percent: float, message: str) -> None:
        self.store.emit(
            task_id,
            "task_progress",
            {"percent": percent, "message": message},
            user_id=str(user_id),
        )

    def emit_completed(self, task_id: str, user_id, result: dict | None = None) -> None:
        self.store.emit(
            task_id, "task_completed", result or {}, user_id=str(user_id)
        )

    def emit_failed(self, task_id: str, user_id, error: str) -> None:
        self.store.emit(
            task_id, "task_failed", {"error": error}, user_id=str(user_id)
        )
