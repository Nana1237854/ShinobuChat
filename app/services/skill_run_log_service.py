"""Compatibility wrapper.

New code should import from:
    app.domains.observability.skill_run_log_service
"""

from app.domains.observability.skill_run_log_service import SkillRunLogService

__all__ = ["SkillRunLogService"]