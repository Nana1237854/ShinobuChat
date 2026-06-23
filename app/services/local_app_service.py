"""Compatibility wrapper.

New code should import from:
    app.domains.local_agent.local_app_service
"""

from app.domains.local_agent.local_app_service import LocalAppService

__all__ = ["LocalAppService"]