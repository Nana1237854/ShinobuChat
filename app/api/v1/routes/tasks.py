"""Task SSE routes (F16).

Provides Server-Sent Events for long-running task progress.
Used by download, Playwright automation, and MCP long tasks.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user_id

router = APIRouter(prefix="/tasks", tags=["tasks"])


class _TaskEventStore:
    """In-memory store for task events. One queue per task_id."""

    def __init__(self) -> None:
        self._queues: dict[str, list[dict]] = defaultdict(list)

    def emit(self, task_id: str, event: str, payload: dict | None = None) -> None:
        entry = {
            "event": event,
            "payload": payload or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._queues[task_id].append(entry)

    def get_events(self, task_id: str) -> list[dict]:
        return self._queues.get(task_id, [])

    def cleanup(self, task_id: str) -> None:
        self._queues.pop(task_id, None)


_task_store = _TaskEventStore()


def emit_task_event(task_id: str, event: str, payload: dict | None = None) -> None:
    _task_store.emit(task_id, event, payload)


@router.get("/{task_id}/events")
async def task_events(
    task_id: str,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> StreamingResponse:
    async def event_generator():
        emitted = 0
        while True:
            if await request.is_disconnected():
                break

            events = _task_store.get_events(task_id)
            while emitted < len(events):
                evt = events[emitted]
                data = json.dumps(evt["payload"], ensure_ascii=False)
                yield f"event: {evt['event']}\ndata: {data}\n\n"
                emitted += 1

            # Check if task completed
            if any(e["event"] in ("task_completed", "task_failed", "task_cancelled")
                   for e in events):
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
