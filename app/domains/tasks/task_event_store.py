"""Task event store — in-memory event queue per task_id."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TaskEvent:
    event: str
    payload: dict
    timestamp: str
    user_id: str | None = None


class TaskEventStore:
    """In-memory store for task events. One queue per task_id."""

    def __init__(self) -> None:
        self._queues: dict[str, list[TaskEvent]] = defaultdict(list)

    def emit(
        self,
        task_id: str,
        event: str,
        payload: dict | None = None,
        user_id: str | None = None,
    ) -> None:
        entry = TaskEvent(
            event=event,
            payload=payload or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
        )
        self._queues[task_id].append(entry)

    def get_events(self, task_id: str, user_id: str | None = None) -> list[TaskEvent]:
        events = self._queues.get(task_id, [])
        if user_id is None:
            return events
        return [e for e in events if e.user_id in (None, user_id)]

    def cleanup(self, task_id: str) -> None:
        self._queues.pop(task_id, None)
