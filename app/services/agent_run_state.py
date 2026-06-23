"""Agent execution state model — used in progress events to report phase."""

from enum import Enum


class AgentRunState(str, Enum):
    PLANNING = "planning"
    TOOL_SELECTING = "tool_selecting"
    TOOL_EXECUTING = "tool_executing"
    VERIFYING = "verifying"
    NEED_USER_CONFIRMATION = "need_user_confirmation"
    FINALIZING = "finalizing"
    FAILED = "failed"
