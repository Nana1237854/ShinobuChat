from __future__ import annotations

import importlib
import json
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from app.models.message import Message
from app.services.http_client import UrllibHttpClient
from app.services.skill_service import Skill, SkillRegistry


@dataclass(frozen=True)
class ToolContext:
    history: list[Message]
    user_skills: dict[str, Skill] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)
    user_id: UUID | None = field(default=None)
    conversation_id: UUID | None = field(default=None)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict, ToolContext], str]

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True)
class VerifiedToolResult:
    output: str
    verified: bool
    reason: str
    checked_fields: dict = field(default_factory=dict)

    def as_tool_message(self) -> str:
        return json.dumps(
            {
                "status": "verified" if self.verified else "verification_failed",
                "output": self.output,
                "verification": self.reason,
                "checked_fields": self.checked_fields,
            },
            ensure_ascii=False,
        )


def _risk_from_checked_fields(checked: dict) -> str:
    if checked.get("has_failure_marker") or checked.get("starts_with_error"):
        return "high"
    if checked.get("result_empty"):
        return "medium"
    if not checked.get("generic_passed", True):
        return "high"
    return "low"


class ToolRegistry:
    def __init__(
        self,
        skill_registry: SkillRegistry,
        http_client: UrllibHttpClient | None = None,
        session_factory: Callable[[], object] | None = None,
    ):
        self.skill_registry = skill_registry
        self.http_client = http_client or UrllibHttpClient()
        self.session_factory = session_factory
        self._tools = {tool.name: tool for tool in self._load_tools()}

    def _load_tools(self) -> list[Tool]:
        package_name = "app.services.tools"
        package = importlib.import_module(package_name)
        tools: list[Tool] = []
        for module_info in pkgutil.iter_modules(package.__path__, f"{package_name}."):
            module = importlib.import_module(module_info.name)
            create_tool = getattr(module, "create_tool", None)
            if create_tool is not None:
                tools.append(create_tool(self))
        return tools

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def render_catalog(self) -> str:
        return "\n".join(
            f"- {tool.name}: {tool.description}"
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        )

    def execute(self, name: str, arguments: dict, context: ToolContext) -> str:
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
        # Phase 3 fix: do NOT clear metadata — it carries message_id, conversation_mode,
        # route_mode and other fields needed by ToolAudit and downstream verifiers.
        # Handlers receive a fresh dict copy to avoid cross-tool pollution.
        return tool.handler(arguments, context)

    def execute_verified(
        self,
        name: str,
        arguments: dict,
        context: ToolContext,
    ) -> VerifiedToolResult:
        import logging

        from app.services.tool_policy_service import ToolPolicyService
        from app.services.tool_verifier import ToolVerifier

        _tlog = logging.getLogger("shinobu.tool_registry")

        conversation_mode = str(context.metadata.get("conversation_mode") or "companion")
        route_mode = str(context.metadata.get("route_mode") or "")

        # ── Policy gate: deny before any tool handler is called ──
        policy = ToolPolicyService().check(
            name,
            arguments,
            conversation_mode=conversation_mode,
            route_mode=route_mode,
        )
        if not policy.allowed:
            result = VerifiedToolResult(
                output="",
                verified=False,
                reason=f"Tool policy denied: {policy.reason}",
                checked_fields={
                    **policy.checked_fields,
                    "policy_allowed": False,
                    "conversation_mode": conversation_mode,
                    "route_mode": route_mode,
                },
            )
            self._record_tool_audit(name, arguments, result, context)
            return result

        output = self.execute(name, arguments, context)
        verification = ToolVerifier(session_factory=self.session_factory).verify(
            name, output, arguments, context
        )
        result = VerifiedToolResult(
            output=output,
            verified=verification.passed,
            reason=verification.reason,
            checked_fields={
                **verification.checked_fields,
                "policy_allowed": True,
                "conversation_mode": conversation_mode,
                "route_mode": route_mode,
            },
        )
        self._record_tool_audit(name, arguments, result, context)
        return result

    def _record_tool_audit(self, name: str, arguments: dict, result: VerifiedToolResult, context: ToolContext) -> None:
        if self.session_factory is None:
            return
        try:
            import logging

            from app.domains.observability.action_audit_service import ActionAuditService

            _tlog2 = logging.getLogger("shinobu.tool_audit")
            db = self.session_factory()
            try:
                checked = result.checked_fields or {}
                ActionAuditService(db).record(
                    source="tool",
                    action_type=name,
                    user_id=context.user_id,
                    conversation_id=context.conversation_id,
                    message_id=context.metadata.get("message_id"),
                    target=str(
                        arguments.get("url")
                        or arguments.get("app_key")
                        or arguments.get("file_path")
                        or ""
                    ),
                    status="ok" if result.verified else "failed",
                    risk_level=_risk_from_checked_fields(checked),
                    requires_confirmation=bool(checked.get("requires_confirmation")),
                    policy_allowed=bool(checked.get("policy_allowed", True)),
                    verified=result.verified,
                    arguments=arguments,
                    result=result.output,
                    reasons=[result.reason],
                    checked_fields=checked,
                )
            finally:
                db.close()
        except Exception:
            import logging

            _tlog3 = logging.getLogger("shinobu.tool_audit")
            _tlog3.warning("Tool audit failed", exc_info=True)
