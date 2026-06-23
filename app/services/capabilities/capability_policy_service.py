"""Compatibility wrapper.

New code should import from:
    app.domains.capabilities.capability_policy_service
"""

from app.domains.capabilities.capability_policy_service import CapabilityPolicyService

__all__ = ["CapabilityPolicyService"]