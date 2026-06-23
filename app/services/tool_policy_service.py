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

# Per-mode allowed tool groups (snake_case tool names map to groups).
# Groups not listed for a mode are denied.
_MODE_TOOL_GROUPS: dict[str, set[str]] = {
    "companion": {"chat", "memory", "reminder", "emotion", "todo", "config_update", "unknown"},
    "work": {"chat", "memory", "reminder", "todo", "goal", "web_search", "config_update", "unknown"},
    "focus": {"todo", "goal", "reminder", "unknown"},
    "night": {"chat", "reminder", "unknown"},
}

# Tool name → group mapping (simple keyword-based classification).
def _classify_tool(tool_name: str) -> str:
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
    ) -> ToolPolicyDecision:
        checked: dict = {
            "tool_name": tool_name,
            "conversation_mode": conversation_mode,
            "route_mode": route_mode or "",
        }

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

        return ToolPolicyDecision(
            True,
            f"Tool policy allowed: '{tool_name}' (group={group}) in {conversation_mode} mode",
            checked_fields={**checked, "rule": "allowed", "tool_group": group},
        )
