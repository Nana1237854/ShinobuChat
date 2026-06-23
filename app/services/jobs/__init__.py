"""JobScheduler — unified background job system (Phase 3).

Replaces raw `while True` loops in main.py with a proper scheduler.
"""

from app.domains.jobs.job_base import BaseJob, JobResult
from app.domains.jobs.job_scheduler import JobScheduler
from app.domains.jobs.job_registry import create_default_scheduler

__all__ = ["BaseJob", "JobResult", "JobScheduler", "create_default_scheduler"]
