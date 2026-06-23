"""SkillRunLogService — persist skill activation records (Phase 3)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.skill_run_log import SkillRunLog


class SkillRunLogService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        user_id: UUID | None = None,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        skill_name: str,
        trigger_source: str,
        matched: bool,
        activated: bool,
        input_text: str = "",
        output_text: str = "",
        error_message: str = "",
        duration_ms: int = 0,
    ) -> SkillRunLog:
        row = SkillRunLog(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            skill_name=skill_name,
            trigger_source=trigger_source,
            matched=matched,
            activated=activated,
            input_summary=self._summary(input_text),
            output_summary=self._summary(output_text),
            error_message=self._summary(error_message, 500),
            duration_ms=duration_ms,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_for_user(self, user_id: UUID, limit: int = 50, offset: int = 0) -> list[SkillRunLog]:
        return (
            self.db.query(SkillRunLog)
            .filter(SkillRunLog.user_id == user_id)
            .order_by(SkillRunLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get(self, run_id: UUID) -> SkillRunLog | None:
        return self.db.query(SkillRunLog).filter(SkillRunLog.id == run_id).first()

    def get_for_user(self, run_id: UUID, user_id: UUID) -> SkillRunLog | None:
        return (
            self.db.query(SkillRunLog)
            .filter(SkillRunLog.id == run_id, SkillRunLog.user_id == user_id)
            .first()
        )

    @staticmethod
    def _summary(text: str, limit: int = 300) -> str:
        clean = " ".join((text or "").split())
        return clean[:limit] + ("...[truncated]" if len(clean) > limit else "")
