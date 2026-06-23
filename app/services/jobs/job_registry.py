"""Job registry — creates the default scheduler with all Phase 3 jobs."""

from __future__ import annotations

from app.services.jobs.diary_generation_job import DiaryGenerationJob
from app.services.jobs.goal_checkin_job import GoalCheckinJob
from app.services.jobs.job_run_log_service import JobRunLogService
from app.services.jobs.job_scheduler import JobScheduler
from app.services.jobs.reminder_scan_job import ReminderScanJob


def create_default_scheduler() -> JobScheduler:
    """Create a JobScheduler with all Phase 3 jobs registered."""
    jobs = [
        ReminderScanJob(),
        GoalCheckinJob(),
        DiaryGenerationJob(),
    ]
    return JobScheduler(jobs, JobRunLogService)
