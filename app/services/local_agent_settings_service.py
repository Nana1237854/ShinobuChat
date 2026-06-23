"""Compatibility wrapper.

New code should import from:
    app.domains.local_agent.local_agent_settings_service
"""

from app.domains.local_agent.local_agent_settings_service import LocalAgentSettingsService

__all__ = ["LocalAgentSettingsService"]