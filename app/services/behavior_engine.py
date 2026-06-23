"""BehaviorEngine — unified behavior decision engine (Phase 3).

Replaces scattered mode/policy/capability logic across AgentCoordinator,
ToolPolicyService, LocalAgentSettingsService, BrowserFacadeService,
VoiceReplyService, MemoryWriteScheduler, ReminderSchedulerService,
MCP Adapter, and DownloadService.

ModeService and LocalAgentSettingsService remain independent services.
BehaviorEngine wraps their logic into a single decide() call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from app.schemas.mode import (
    ConversationMode,
    ModeDecisionTendency,
    ModeReminderPolicy,
    ModeReplyPolicy,
    ModeToolPolicy,
)
from app.services.mode_service import (
    DECISION_TENDENCIES,
    REMINDER_POLICIES,
    REPLY_POLICIES,
    ROLEPLAY_PROMPT_SECTIONS,
    TOOL_POLICIES,
)

logger = logging.getLogger("shinobu.behavior_engine")


@dataclass(frozen=True)
class BehaviorContext:
    user_id: str
    conversation_id: str | None = None
    route_mode: str = "auto"
    conversation_mode: str = "companion"

    user_emotion: str | None = None
    time_of_day: str | None = None

    active_goals_count: int = 0
    recent_message_count: int = 0
    has_due_reminders: bool = False

    local_agent_settings: dict = field(default_factory=dict)
    runtime_config: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityDecision:
    enabled: bool
    requires_confirmation: bool = False
    reason: str = ""


@dataclass(frozen=True)
class BehaviorDecision:
    conversation_mode: str

    reply_length: Literal["minimal", "short", "medium", "long"] = "short"
    proactive_level: Literal["none", "low", "normal", "high"] = "normal"

    allowed_tool_groups: list[str] = field(default_factory=list)
    blocked_tool_groups: list[str] = field(default_factory=list)

    capabilities: dict[str, CapabilityDecision] = field(default_factory=dict)

    reminder_style: str = "friendly"
    memory_write_policy: Literal["off", "conservative", "normal", "aggressive"] = "normal"
    tts_style: str = "neutral"

    should_suppress_idle_chat: bool = False
    should_prefer_todo: bool = False
    should_prefer_goal: bool = False
    should_prefer_task_planning: bool = False

    prompt_hints: list[str] = field(default_factory=list)
    debug_reasons: list[str] = field(default_factory=list)


class BehaviorEngine:
    """Unified behavior decision engine.

    Produces a single BehaviorDecision from a BehaviorContext,
    consolidating mode, tool policy, reply policy, reminder policy,
    capability gates, TTS style, and prompt hints.
    """

    def __init__(self):
        pass

    def decide(self, context: BehaviorContext) -> BehaviorDecision:
        mode = context.conversation_mode or "companion"

        tool_policy = self._get_tool_policy(mode)
        reply_policy = self._get_reply_policy(mode)
        reminder_policy = self._get_reminder_policy(mode)
        tendency = self._get_decision_tendency(mode)

        prompt_hints: list[str] = []
        debug_reasons: list[str] = [f"mode={mode}"]

        # Mode prompt hints
        if mode == "work":
            prompt_hints.append("当前处于工作模式，回复需结构化，优先给出结论、步骤或清单。")
        elif mode == "focus":
            prompt_hints.append("当前处于专注模式，只回应用户明确提出的问题，不主动展开闲聊。")
        elif mode == "night":
            prompt_hints.append("当前处于夜间模式，语气更轻，回复更短更温暖，减少打扰感。")
        else:
            prompt_hints.append("当前处于陪伴模式，语气自然、温暖、有陪伴感。")

        # Emotion-aware hints
        if context.user_emotion in {"stressed", "tired", "worried", "lonely"}:
            prompt_hints.append("用户可能处于低能量状态，回复要更温柔、简洁，避免压迫感。")
            debug_reasons.append(f"emotion={context.user_emotion}")

        capabilities = self._capability_decisions(context, mode)

        return BehaviorDecision(
            conversation_mode=mode,
            reply_length=self._reply_length(reply_policy.max_sentences),
            proactive_level=self._proactive_level(mode, context),
            allowed_tool_groups=tool_policy.allowed_tool_groups,
            blocked_tool_groups=tool_policy.blocked_tool_groups,
            capabilities=capabilities,
            reminder_style=reminder_policy.tone,
            memory_write_policy=self._memory_policy(mode),
            tts_style=self._tts_style(mode, context.user_emotion),
            should_suppress_idle_chat=tendency.suppress_idle_chat,
            should_prefer_todo=tendency.prefer_todo_create,
            should_prefer_goal=mode in {"work", "focus"},
            should_prefer_task_planning=tendency.prefer_task_planning,
            prompt_hints=prompt_hints,
            debug_reasons=debug_reasons,
        )

    # ── Capability decisions ──

    def _capability_decisions(
        self, context: BehaviorContext, mode: str
    ) -> dict[str, CapabilityDecision]:
        settings = context.local_agent_settings or {}

        return {
            "local_launcher": CapabilityDecision(
                enabled=bool(settings.get("local_launcher_enabled", True)),
                requires_confirmation=False,
                reason="Controlled by local_agent_settings.local_launcher_enabled",
            ),
            "browser_reader": CapabilityDecision(
                enabled=bool(settings.get("browser_reader_enabled", True)),
                requires_confirmation=bool(settings.get("require_confirm_for_unknown_url", True)),
                reason="Browser Reader permission toggle",
            ),
            "browser_automation": CapabilityDecision(
                enabled=bool(settings.get("browser_automation_enabled", False)),
                requires_confirmation=True,
                reason="Browser Automation is high-risk and defaults to off",
            ),
            "mcp": CapabilityDecision(
                enabled=bool(settings.get("mcp_enabled", False)),
                requires_confirmation=False,
                reason="MCP adapter defaults to off",
            ),
            "download": CapabilityDecision(
                enabled=True,
                requires_confirmation=bool(settings.get("require_confirm_for_executable", True)),
                reason="Download safety classifier controls per-candidate risk",
            ),
        }

    # ── Policy helpers ──

    def _get_tool_policy(self, mode: str) -> ModeToolPolicy:
        return TOOL_POLICIES.get(mode, TOOL_POLICIES["companion"])

    def _get_reply_policy(self, mode: str) -> ModeReplyPolicy:
        return REPLY_POLICIES.get(mode, REPLY_POLICIES["companion"])

    def _get_reminder_policy(self, mode: str) -> ModeReminderPolicy:
        return REMINDER_POLICIES.get(mode, REMINDER_POLICIES["companion"])

    def _get_decision_tendency(self, mode: str) -> ModeDecisionTendency:
        return DECISION_TENDENCIES.get(mode, DECISION_TENDENCIES["companion"])

    def _reply_length(self, max_sentences: int) -> str:
        if max_sentences <= 1:
            return "minimal"
        if max_sentences <= 3:
            return "short"
        if max_sentences <= 5:
            return "medium"
        return "long"

    def _proactive_level(self, mode: str, context: BehaviorContext) -> str:
        if mode in {"focus", "night"}:
            return "low"
        if context.user_emotion in {"tired", "stressed"}:
            return "low"
        return "normal"

    def _memory_policy(self, mode: str) -> str:
        if mode in {"focus", "night"}:
            return "conservative"
        return "normal"

    def _tts_style(self, mode: str, emotion: str | None) -> str:
        if mode == "night":
            return "soft"
        if emotion in {"tired", "worried", "lonely"}:
            return "gentle"
        if mode == "work":
            return "clear"
        return "neutral"


def build_roleplay_prompt_section(mode: str) -> str:
    """Legacy-compatible helper. Returns the roleplay prompt section for a mode."""
    return ROLEPLAY_PROMPT_SECTIONS.get(mode, "")
