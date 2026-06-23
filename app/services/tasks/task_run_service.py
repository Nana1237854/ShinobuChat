"""Compatibility wrapper.

New code should import from:
    app.domains.tasks.task_run_service
"""

from app.domains.tasks.task_run_service import TaskRunService

__all__ = ["TaskRunService"]