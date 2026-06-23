"""DiaryGenerationJob — periodic auto-diary generation (Phase 3)."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.jobs.job_base import BaseJob, JobResult

logger = logging.getLogger("shinobu.jobs.diary_generation")


class DiaryGenerationJob(BaseJob):
    name = "diary_auto_generation"

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.enabled = settings.diary_auto_generate_enabled
        self.interval_seconds = settings.diary_background_scan_interval_seconds

    def run_once(self) -> JobResult:
        db = self.session_factory()
        try:
            from app.services.diary_scheduler_service import DiarySchedulerService

            svc = DiarySchedulerService(db)
            generated = svc.scan_and_generate()
            return JobResult(
                status="success",
                summary=f"Auto diary generated for {generated} users",
                data={"generated": generated},
            )
        finally:
            db.close()
