"""Compatibility wrapper.

New code should import from:
    app.domains.jobs.reminder_scan_job
"""

from app.domains.jobs.reminder_scan_job import ReminderScanJob

__all__ = ["ReminderScanJob"]