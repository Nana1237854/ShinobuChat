from __future__ import annotations

import json
import logging
from typing import Any, Iterator
from uuid import UUID

from app.core.config import settings
from app.models.message import Message
from app.services.agent_service import AgentService
from app.services.ai_client import AIClient
from app.services.skill_service import Skill
from app.services.stream_events import StreamEvent
from app.services.tool_registry import ToolContext, ToolRegistry
from app.services.tool_registry import VerifiedToolResult

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(
        self,
        agent_service: AgentService,
        tool_registry: ToolRegistry,
        ai_client: AIClient,
    ):
        self.agent_service = agent_service
        self.tool_registry = tool_registry
        self.ai_client = ai_client

    def verify_step(
        self,
        tool_name: str,
        verified: VerifiedToolResult,
    ) -> None:
        """Log verification result and yield honest failure message if needed.

        Verification is performed by ToolRegistry.execute_verified — this method
        only handles logging and user-facing messaging.
        """
        logger.info(
            "verify_step tool=%s ok=%s reason=%s checked_fields=%s",
            tool_name,
            verified.verified,
            verified.reason,
            verified.checked_fields,
        )
        if not verified.verified:
            logger.warning(
                "Tool verification failed for %s: %s (checked: %s)",
                tool_name,
                verified.reason,
                verified.checked_fields,
            )

    def run(
        self,
        messages: list[dict],
        history: list[Message],
        *,
        user_skills: list[Skill] | None = None,
        ai_config: dict[str, Any] | None = None,
        conversation_mode: str = "companion",
        route_mode: str | None = None,
        user_id: UUID | None = None,
        conversation_id: UUID | None = None,
    ) -> Iterator[StreamEvent | str]:
        tools = self.tool_registry.schemas()
        context = ToolContext(
            history=history,
            user_skills={skill.name: skill for skill in user_skills or []},
            metadata={
                "conversation_mode": conversation_mode,
                "route_mode": route_mode or "agent",
            },
            user_id=user_id,
            conversation_id=conversation_id,
        )
        for step in range(max(settings.agent_max_steps, 1)):
            yield StreamEvent(
                "progress",
                {
                    "skill_name": "agent",
                    "message": f"Thinking step {step + 1}",
                    "percent": min(0.25 + step * 0.1, 0.85),
                },
            )
            assistant_message = self.ai_client.complete_chat(
                messages,
                tools=tools,
                max_tokens=int(
                    (ai_config or {}).get(
                        "ai_lightweight_max_tokens", settings.ai_lightweight_max_tokens
                    )
                ),
                runtime_config=ai_config,
            )
            tool_calls = assistant_message.get("tool_calls") or []
            content = assistant_message.get("content") or ""
            if not tool_calls:
                if content:
                    yield StreamEvent("chunk", {"delta": content})
                yield content
                return

            messages.append(assistant_message)
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name = function.get("name", "unknown")
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                yield StreamEvent(
                    "progress",
                    {
                        "skill_name": tool_name,
                        "message": "Running tool",
                        "percent": min(0.35 + step * 0.1, 0.9),
                    },
                )
                result = self.tool_registry.execute_verified(tool_name, arguments, context)

                # Log and handle verification result (single verification path)
                self.verify_step(tool_name, result)

                if not result.verified:
                    yield StreamEvent(
                        "error",
                        {
                            "code": "TOOL_VERIFICATION_FAILED",
                            "hint": f"{tool_name}: {result.reason}",
                            "checked_fields": result.checked_fields,
                        },
                    )
                    yield StreamEvent(
                        "chunk",
                        {
                            "delta": (
                                "我尝试了，但没有确认成功。"
                                f"{tool_name} 工具执行后验证失败：{result.reason}"
                            ),
                        },
                    )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "content": result.as_tool_message(),
                    }
                )

        fallback = "Agent step limit reached. Please narrow the task or add more specific context."
        yield StreamEvent("chunk", {"delta": fallback})
        yield fallback
