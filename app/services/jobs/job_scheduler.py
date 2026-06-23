"""JobScheduler — async background job orchestrator (Phase 3).

Runs registered BaseJob instances on configurable intervals.
Job failures are logged (JobRunLog) but never propagate to the main app.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.time import local_now
from app.services.jobs.job_base import BaseJob

logger = logging.getLogger("shinobu.jobs")


class JobScheduler:
    def __init__(self, jobs: list[BaseJob], log_service):
        self.jobs = [j for j in jobs if j.enabled]
        self.log_service = log_service
        self._tasks: list[asyncio.Task] = []
        self._stopped = False

    def start(self):
        for job in self.jobs:
            task = asyncio.create_task(self._run_loop(job))
            self._tasks.append(task)
        logger.info("JobScheduler started with %d jobs", len(self.jobs))

    async def stop(self):
        self._stopped = True
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("JobScheduler stopped")

    async def _run_loop(self, job: BaseJob):
        while not self._stopped:
            await self.run_once(job)
            try:
                await asyncio.sleep(job.interval_seconds)
            except asyncio.CancelledError:
                break

    async def run_once(self, job: BaseJob):
        from app.db.session import SessionLocal

        started_at = local_now()
        try:
            result = await asyncio.to_thread(job.run_once)
            db = SessionLocal()
            try:
                self.log_service.__class__(db).record_success(job.name, started_at, result)
            finally:
                db.close()
        except Exception as exc:
            logger.exception("Job failed: %s", job.name)
            try:
                db = SessionLocal()
                try:
                    self.log_service.__class__(db).record_failure(job.name, started_at, exc)
                finally:
                    db.close()
            except Exception:
                logger.warning("Job failure log write failed for %s", job.name, exc_info=True)

    def run_once_for_test(self, job: BaseJob):
        """Synchronous run-once for tests."""
        from app.db.session import SessionLocal

        started_at = local_now()
        try:
            result = job.run_once()
            db = SessionLocal()
            try:
                self.log_service.__class__(db).record_success(job.name, started_at, result)
            finally:
                db.close()
        except Exception as exc:
            try:
                db = SessionLocal()
                try:
                    self.log_service.__class__(db).record_failure(job.name, started_at, exc)
                finally:
                    db.close()
            except Exception:
                logger.warning("Job failure log write failed for %s", job.name, exc_info=True)
