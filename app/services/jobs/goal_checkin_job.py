"""GoalCheckinJob — periodic goal checkin scanner (Phase 3)."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.jobs.job_base import BaseJob, JobResult

logger = logging.getLogger("shinobu.jobs.goal_checkin")


class GoalCheckinJob(BaseJob):
    name = "goal_checkin_scan"

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.enabled = settings.reminder_background_enabled
        self.interval_seconds = settings.reminder_scan_interval_seconds

    def run_once(self) -> JobResult:
        db = self.session_factory()
        try:
            from app.services.goal_service import GoalService

            svc = GoalService(db)
            events = svc.scan_due_checkins()
            return JobResult(
                status="success",
                summary=f"Goal checkin scan produced {len(events)} events",
                data={"count": len(events)},
            )
        finally:
            db.close()
