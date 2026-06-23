"""ReminderScanJob — periodic due-reminder scanner (Phase 3)."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.jobs.job_base import BaseJob, JobResult

logger = logging.getLogger("shinobu.jobs.reminder_scan")


class ReminderScanJob(BaseJob):
    name = "reminder_scan"

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.enabled = settings.reminder_background_enabled
        self.interval_seconds = settings.reminder_scan_interval_seconds

    def run_once(self) -> JobResult:
        db = self.session_factory()
        try:
            from app.services.mode_service import ModeService
            from app.services.reminder_scheduler_service import ReminderSchedulerService

            mode_svc = ModeService(db)
            service = ReminderSchedulerService(db, mode_service=mode_svc)
            events = service.scan_due_reminders()
            return JobResult(
                status="success",
                summary=f"Reminder scan produced {len(events)} events",
                data={"count": len(events)},
            )
        finally:
            db.close()
