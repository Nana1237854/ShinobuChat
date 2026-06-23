"""Job registry — creates the default scheduler with all Phase 3 jobs."""

from __future__ import annotations

from app.domains.jobs.diary_generation_job import DiaryGenerationJob
from app.domains.jobs.goal_checkin_job import GoalCheckinJob
from app.domains.jobs.job_run_log_service import JobRunLogService
from app.domains.jobs.job_scheduler import JobScheduler
from app.domains.jobs.reminder_scan_job import ReminderScanJob


def create_default_scheduler() -> JobScheduler:
    """Create a JobScheduler with all Phase 3 jobs registered."""
    jobs = [
        ReminderScanJob(),
        GoalCheckinJob(),
        DiaryGenerationJob(),
    ]
    return JobScheduler(jobs, JobRunLogService)
