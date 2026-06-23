"""Compatibility wrapper.

New code should import from:
    app.domains.jobs.job_run_log_service
"""

from app.domains.jobs.job_run_log_service import JobRunLogService

__all__ = ["JobRunLogService"]