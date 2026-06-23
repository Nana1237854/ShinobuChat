"""Compatibility wrapper.

New code should import from:
    app.domains.jobs.job_scheduler
"""

from app.domains.jobs.job_scheduler import JobScheduler

__all__ = ["JobScheduler"]