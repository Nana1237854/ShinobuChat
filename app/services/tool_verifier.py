from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.tool_registry import ToolContext


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    reason: str


class ToolVerifier:
    def verify(self, tool_name: str, result: str, context: "ToolContext") -> VerificationResult:
        normalized = (result or "").strip()
        if not normalized:
            return VerificationResult(False, "tool returned an empty result")

        lowered = normalized.lower()
        failure_markers = (
            "error:",
            "failed",
            "timed out",
            "rejected:",
            "not found",
            "unknown tool",
        )
        if any(marker in lowered for marker in failure_markers):
            return VerificationResult(False, "tool result contains an explicit failure state")

        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and (payload.get("error") or payload.get("status") == "error"):
            return VerificationResult(False, "tool returned an error payload")

        if tool_name == "shell_command":
            exit_code = context.metadata.get("exit_code")
            if exit_code is None:
                return VerificationResult(False, "shell command did not report an exit code")
            if exit_code != 0:
                return VerificationResult(False, f"shell command exited with code {exit_code}")

        return VerificationResult(True, "verification passed")
