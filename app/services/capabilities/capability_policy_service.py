"""CapabilityPolicyService — per-user capability gating (Phase 3).

Wraps LocalAgentSettingsService for per-user permission checks.
BrowserFacadeService, MCP status, and LocalAppService all converge here.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.services.behavior_engine import CapabilityDecision
from app.services.capabilities.capability_registry import CapabilityRegistry
from app.services.local_agent_settings_service import LocalAgentSettingsService


class CapabilityPolicyService:
    def __init__(self, db: Session):
        self.db = db
        self.registry = CapabilityRegistry()
        self.settings = LocalAgentSettingsService(db)

    def check(self, user_id: UUID, capability_key: str) -> CapabilityDecision:
        capability = self.registry.get(capability_key)
        if capability is None:
            return CapabilityDecision(False, True, "Unknown capability")

        settings = self.settings.get_settings(user_id)

        if capability_key == "local_launcher":
            enabled = settings.get("local_launcher_enabled", capability.default_enabled)
        elif capability_key == "browser_reader":
            enabled = settings.get("browser_reader_enabled", capability.default_enabled)
        elif capability_key == "browser_automation":
            enabled = settings.get("browser_automation_enabled", capability.default_enabled)
        elif capability_key == "mcp":
            enabled = settings.get("mcp_enabled", capability.default_enabled)
        else:
            enabled = capability.default_enabled

        return CapabilityDecision(
            enabled=bool(enabled),
            requires_confirmation=capability.requires_confirmation_by_default,
            reason=f"{capability.label} capability is {'enabled' if enabled else 'disabled'}",
        )

    def ensure(self, user_id: UUID, capability_key: str) -> CapabilityDecision:
        decision = self.check(user_id, capability_key)
        if not decision.enabled:
            raise ForbiddenError(decision.reason)
        return decision
