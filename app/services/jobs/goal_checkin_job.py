"""Compatibility wrapper.

New code should import from:
    app.domains.jobs.goal_checkin_job
"""

from app.domains.jobs.goal_checkin_job import GoalCheckinJob

__all__ = ["GoalCheckinJob"]