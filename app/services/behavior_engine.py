"""Compatibility wrapper.

New code should import from:
    app.domains.agent.behavior_engine
"""

from app.domains.agent.behavior_engine import (
    BehaviorContext,
    BehaviorDecision,
    CapabilityDecision,
    BehaviorEngine,
    build_roleplay_prompt_section,
)

__all__ = [
    "BehaviorContext",
    "BehaviorDecision",
    "CapabilityDecision",
    "BehaviorEngine",
    "build_roleplay_prompt_section",
]