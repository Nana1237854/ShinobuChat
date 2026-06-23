"""JobRunLogService — persist job execution records (Phase 3)."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.time import local_now
from app.models.job_run_log import JobRunLog

logger = logging.getLogger("shinobu.job_run_log")


class JobRunLogService:
    def __init__(self, db: Session):
        self.db = db

    def record_success(self, job_name: str, started_at: datetime, result) -> JobRunLog:
        finished = local_now()
        duration = int((finished - started_at).total_seconds() * 1000)

        summary = getattr(result, "summary", "") if result else ""
        row = JobRunLog(
            job_name=job_name,
            status="success",
            started_at=started_at,
            finished_at=finished,
            duration_ms=duration,
            result_summary=summary[:1000],
        )
        self.db.add(row)
        self.db.commit()
        return row

    def record_failure(self, job_name: str, started_at: datetime, exc: Exception) -> JobRunLog:
        finished = local_now()
        duration = int((finished - started_at).total_seconds() * 1000)

        row = JobRunLog(
            job_name=job_name,
            status="failed",
            started_at=started_at,
            finished_at=finished,
            duration_ms=duration,
            error_message=str(exc)[:1000],
        )
        self.db.add(row)
        self.db.commit()
        return row

    def list_for_job(self, job_name: str, limit: int = 50) -> list[JobRunLog]:
        return (
            self.db.query(JobRunLog)
            .filter(JobRunLog.job_name == job_name)
            .order_by(JobRunLog.started_at.desc())
            .limit(limit)
            .all()
        )

    def list_all(self, limit: int = 100) -> list[JobRunLog]:
        return (
            self.db.query(JobRunLog)
            .order_by(JobRunLog.started_at.desc())
            .limit(limit)
            .all()
        )

    def get(self, run_id) -> JobRunLog | None:
        return self.db.query(JobRunLog).filter(JobRunLog.id == run_id).first()
