from __future__ import annotations

import json
from typing import Iterator

from app.core.config import settings
from app.models.message import Message
from app.services.agent_service import AgentService
from app.services.ai_client import AIClient
from app.services.stream_events import StreamEvent
from app.services.tool_registry import ToolContext, ToolRegistry


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

    def run(self, messages: list[dict], history: list[Message]) -> Iterator[StreamEvent | str]:
        tools = self.tool_registry.schemas()
        context = ToolContext(history=history)
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
                max_tokens=settings.ai_lightweight_max_tokens,
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
                result = self.tool_registry.execute(tool_name, arguments, context)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "content": result,
                    }
                )

        fallback = "Agent step limit reached. Please narrow the task or add more specific context."
        yield StreamEvent("chunk", {"delta": fallback})
        yield fallback
