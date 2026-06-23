"""Browser action log service — records browser operations to BrowserActionLog."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.time import local_now
from app.models.browser_action_log import BrowserActionLog


class BrowserActionLogService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        user_id: UUID,
        action_type: str,
        target_url: str | None = None,
        status: str = "started",
        message: str | None = None,
        error_detail: str | None = None,
        payload_json: dict | None = None,
    ) -> BrowserActionLog:
        log = BrowserActionLog(
            user_id=user_id,
            action_type=action_type,
            target_url=target_url,
            status=status,
            message=message,
            error_detail=error_detail,
            payload_json=payload_json or {},
            finished_at=local_now() if status in ("ok", "error", "failed") else None,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_logs(
        self,
        user_id: UUID,
        action_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BrowserActionLog]:
        q = self.db.query(BrowserActionLog).filter(
            BrowserActionLog.user_id == user_id
        )
        if action_type:
            q = q.filter(BrowserActionLog.action_type == action_type)
        if status:
            q = q.filter(BrowserActionLog.status == status)
        return (
            q.order_by(BrowserActionLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
