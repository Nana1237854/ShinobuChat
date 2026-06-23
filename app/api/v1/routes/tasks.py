"""Task SSE routes (F16).

Provides Server-Sent Events for long-running task progress.
Used by download, Playwright automation, and MCP long tasks.
"""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.services.tasks.task_event_store import TaskEventStore
from app.services.tasks.task_event_service import TaskEventService
from app.services.tasks.task_run_service import TaskRunService

router = APIRouter(prefix="/tasks", tags=["tasks"])

task_event_store = TaskEventStore()
task_event_service = TaskEventService(task_event_store)


def emit_task_event(
    task_id: str,
    event: str,
    payload: dict | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    task_event_store.emit(
        task_id, event, payload,
        user_id=str(user_id) if user_id else None,
    )


# ── Phase 3: TaskRun metadata endpoints ──

@router.get("")
def list_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    rows = TaskRunService(db, task_event_service).list_for_user(
        user_id, limit=limit, offset=offset,
    )
    return {
        "tasks": [
            {
                "id": r.id,
                "task_type": r.task_type,
                "status": r.status,
                "title": r.title,
                "progress": r.progress,
                "message": r.message,
                "result_summary": r.result_summary,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in rows
        ]
    }


@router.get("/{task_id}")
def get_task(
    task_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    r = TaskRunService(db, task_event_service).get_for_user(task_id, user_id)
    return {
        "id": r.id,
        "task_type": r.task_type,
        "status": r.status,
        "title": r.title,
        "progress": r.progress,
        "message": r.message,
        "result_summary": r.result_summary,
        "error_message": r.error_message,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


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

            events = task_event_store.get_events(task_id, user_id=str(user_id))

            while emitted < len(events):
                evt = events[emitted]
                data = json.dumps(evt.payload, ensure_ascii=False)
                yield f"event: {evt.event}\ndata: {data}\n\n"
                emitted += 1

            if any(e.event in ("task_completed", "task_failed", "task_cancelled")
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
