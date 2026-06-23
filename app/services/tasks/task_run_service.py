"""TaskRunService — persist task lifecycle events (Phase 3).

Workflows:
- create() writes a pending TaskRun and emits task_started.
- update_progress() transitions status to 'running'.
- complete() writes status='completed', progress=1.0.
- fail() writes status='failed' with error message.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.time import local_now
from app.models.task_run import TaskRun
from app.services.tasks.task_event_service import TaskEventService


class TaskRunService:
    def __init__(self, db: Session, event_service: TaskEventService):
        self.db = db
        self.events = event_service

    def create(self, *, task_id: str, user_id: UUID, task_type: str, title: str) -> TaskRun:
        row = TaskRun(
            id=task_id,
            user_id=user_id,
            task_type=task_type,
            title=title,
            status="pending",
            progress=0.0,
        )
        self.db.add(row)
        self.db.commit()
        self.events.emit_started(task_id, user_id, title)
        return row

    def update_progress(self, task_id: str, user_id: UUID, percent: float, message: str) -> TaskRun:
        row = self._get_owned(task_id, user_id)
        row.status = "running"
        row.progress = percent
        row.message = message
        row.updated_at = local_now()
        self.db.commit()
        self.events.emit_progress(task_id, user_id, percent, message)
        return row

    def complete(self, task_id: str, user_id: UUID, result_summary: str = "") -> TaskRun:
        row = self._get_owned(task_id, user_id)
        row.status = "completed"
        row.progress = 1.0
        row.result_summary = result_summary
        row.finished_at = local_now()
        self.db.commit()
        self.events.emit_completed(task_id, user_id, {"summary": result_summary})
        return row

    def fail(self, task_id: str, user_id: UUID, error: str) -> TaskRun:
        row = self._get_owned(task_id, user_id)
        row.status = "failed"
        row.error_message = error[:1000]
        row.finished_at = local_now()
        self.db.commit()
        self.events.emit_failed(task_id, user_id, error)
        return row

    def list_for_user(self, user_id: UUID, limit: int = 50, offset: int = 0) -> list[TaskRun]:
        return (
            self.db.query(TaskRun)
            .filter(TaskRun.user_id == user_id)
            .order_by(TaskRun.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_for_user(self, task_id: str, user_id: UUID) -> TaskRun:
        row = (
            self.db.query(TaskRun)
            .filter(TaskRun.id == task_id, TaskRun.user_id == user_id)
            .first()
        )
        if not row:
            raise NotFoundError("Task not found")
        return row

    def _get_owned(self, task_id: str, user_id: UUID) -> TaskRun:
        return self.get_for_user(task_id, user_id)
