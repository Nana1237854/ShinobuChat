from __future__ import annotations

from dataclasses import dataclass, field

# Tools that are unconditionally denied regardless of mode.
_ALWAYS_DENIED: set[str] = {
    "shell",
    "shell_command",
    "terminal",
    "exec",
    "execute",
    "file_delete",
    "file_write_outside_workspace",
    "browse_private",
}

# Tools whose group is EXPLICITLY declared here, bypassing keyword classification.
# open_local_app MUST be listed here to avoid falling into the "unknown" group.
_EXPLICIT_TOOL_GROUPS: dict[str, str] = {
    "open_local_app": "local_app",
    "open_url": "browser_open",
    "read_webpage": "web_search",
    "search_web": "web_search",
}

# Per-mode allowed tool groups (snake_case tool names map to groups).
# Groups not listed for a mode are denied.
_MODE_TOOL_GROUPS: dict[str, set[str]] = {
    "companion": {"chat", "memory", "reminder", "emotion", "todo", "config_update", "local_app", "browser_open", "unknown"},
    "work": {"chat", "memory", "reminder", "todo", "goal", "web_search", "config_update", "local_app", "browser_open", "unknown"},
    "focus": {"todo", "goal", "reminder", "local_app", "unknown"},
    "night": {"chat", "reminder", "local_app", "unknown"},
}

# Tool name → group mapping (simple keyword-based classification).
def _classify_tool(tool_name: str) -> str:
    # Explicit assignments take priority over keyword matching
    if tool_name in _EXPLICIT_TOOL_GROUPS:
        return _EXPLICIT_TOOL_GROUPS[tool_name]

    lowered = tool_name.lower().replace("_", "")
    if "todo" in lowered:
        return "todo"
    if "goal" in lowered:
        return "goal"
    if "remind" in lowered:
        return "reminder"
    if "search" in lowered or "fetch" in lowered or "web" in lowered:
        return "web_search"
    if "memory" in lowered:
        return "memory"
    if "emotion" in lowered:
        return "emotion"
    if "chat" in lowered:
        return "chat"
    if "config" in lowered:
        return "config_update"
    return "unknown"


@dataclass(frozen=True)
class ToolPolicyDecision:
    allowed: bool
    reason: str
    checked_fields: dict = field(default_factory=dict)


class ToolPolicyService:
    def check(
        self,
        tool_name: str,
        arguments: dict,
        *,
        conversation_mode: str = "companion",
        route_mode: str | None = None,
        behavior_decision=None,  # Phase 3: BehaviorDecision | None
    ) -> ToolPolicyDecision:
        checked: dict = {
            "tool_name": tool_name,
            "conversation_mode": conversation_mode,
            "route_mode": route_mode or "",
        }

        # Rule 0: BehaviorEngine override (Phase 3)
        if behavior_decision is not None:
            group = _classify_tool(tool_name)
            allowed = set(behavior_decision.allowed_tool_groups)
            blocked = set(behavior_decision.blocked_tool_groups)

            if group in blocked:
                return ToolPolicyDecision(
                    False,
                    f"Tool policy denied: '{tool_name}' (group={group}) blocked by BehaviorEngine",
                    checked_fields={**checked, "rule": "behavior_engine_blocked", "tool_group": group},
                )
            if group not in allowed:
                return ToolPolicyDecision(
                    False,
                    f"Tool policy denied: '{tool_name}' (group={group}) not allowed by BehaviorEngine",
                    checked_fields={**checked, "rule": "behavior_engine_not_allowed", "tool_group": group,
                                    "allowed_groups": sorted(allowed)},
                )
            # BehaviorEngine allowed — skip mode-specific rules
            return ToolPolicyDecision(
                True,
                f"Tool policy allowed by BehaviorEngine: '{tool_name}' (group={group})",
                checked_fields={**checked, "rule": "behavior_engine_allowed", "tool_group": group},
            )

        # ── Legacy mode logic below (when behavior_decision is None) ──

        # Rule 1: unconditionally denied tools
        if tool_name.lower() in _ALWAYS_DENIED:
            return ToolPolicyDecision(
                False,
                f"Tool policy denied: '{tool_name}' is blocked for all modes",
                checked_fields={**checked, "rule": "always_denied"},
            )

        # Rule 2: mode-aware group check
        group = _classify_tool(tool_name)
        allowed_groups = _MODE_TOOL_GROUPS.get(conversation_mode, _MODE_TOOL_GROUPS.get("companion", set()))
        if group not in allowed_groups:
            return ToolPolicyDecision(
                False,
                f"Tool policy denied: '{tool_name}' (group={group}) not allowed in {conversation_mode} mode",
                checked_fields={**checked, "rule": "mode_group_denied", "tool_group": group,
                                "allowed_groups": sorted(allowed_groups)},
            )

        # Rule 3: focus mode — suppress high-distraction tools
        if conversation_mode == "focus" and group in {"chat", "emotion"}:
            return ToolPolicyDecision(
                False,
                f"Tool policy denied: '{tool_name}' is high-distraction, blocked in focus mode",
                checked_fields={**checked, "rule": "focus_suppression"},
            )

        # Rule 4: night mode — suppress active/soliciting tools
        if conversation_mode == "night" and group in {"todo", "goal", "web_search"}:
            return ToolPolicyDecision(
                False,
                f"Tool policy denied: '{tool_name}' is active/soliciting, blocked in night mode",
                checked_fields={**checked, "rule": "night_suppression"},
            )

        # Rule 5: focus mode — restrict entertainment local_app intents
        if conversation_mode == "focus" and group == "local_app":
            intent = str(arguments.get("intent_type") or "").lower()
            entertainment_intents = {"open_music"}
            if intent in entertainment_intents:
                return ToolPolicyDecision(
                    False,
                    f"Tool policy denied: '{tool_name}' intent_type='{intent}' is entertainment, "
                    f"blocked in focus mode",
                    checked_fields={**checked, "rule": "focus_entertainment_blocked", "intent_type": intent},
                )

        # Rule 6: night mode — local_app allowed but requires confirmation for entertainment
        if conversation_mode == "night" and group == "local_app":
            intent = str(arguments.get("intent_type") or "").lower()
            if intent in {"open_music"}:
                return ToolPolicyDecision(
                    True,
                    f"Tool policy allowed with confirmation: '{tool_name}' (group={group}) "
                    f"in {conversation_mode} mode, entertainment intent requires confirmation",
                    checked_fields={
                        **checked, "rule": "allowed_with_confirmation",
                        "tool_group": group, "intent_type": intent,
                        "requires_confirmation": True,
                    },
                )

        return ToolPolicyDecision(
            True,
            f"Tool policy allowed: '{tool_name}' (group={group}) in {conversation_mode} mode",
            checked_fields={**checked, "rule": "allowed", "tool_group": group},
        )
