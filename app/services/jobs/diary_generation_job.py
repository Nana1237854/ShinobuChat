"""Compatibility wrapper.

New code should import from:
    app.domains.jobs.diary_generation_job
"""

from app.domains.jobs.diary_generation_job import DiaryGenerationJob

__all__ = ["DiaryGenerationJob"]