"""CapabilityRegistry — unified capability catalog (Phase 3).

Lists all platform capabilities with risk metadata and default enablement.
CapabilityPolicyService wraps LocalAgentSettingsService for per-user gating.
"""

from app.domains.capabilities.capability_registry import Capability, CapabilityRegistry
from app.domains.capabilities.capability_policy_service import CapabilityPolicyService

__all__ = ["Capability", "CapabilityRegistry", "CapabilityPolicyService"]
