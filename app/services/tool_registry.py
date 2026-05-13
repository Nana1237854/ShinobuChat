from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from typing import Callable
from urllib import parse

from app.core.config import settings
from app.models.message import Message
from app.services.http_client import HttpClientError, UrllibHttpClient
from app.services.skill_service import SkillRegistry


@dataclass(frozen=True)
class ToolContext:
    history: list[Message]


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


class ToolRegistry:
    def __init__(self, skill_registry: SkillRegistry, http_client: UrllibHttpClient | None = None):
        self.skill_registry = skill_registry
        self.http_client = http_client or UrllibHttpClient()
        self._tools = {
            tool.name: tool
            for tool in (
                Tool(
                    name="activate_skill",
                    description="Load a local SKILL.md by skill name and return its instructions.",
                    parameters={
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                    handler=self._activate_skill,
                ),
                Tool(
                    name="fetch_web_page",
                    description="Fetch a webpage and return text content for summarization.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "max_chars": {"type": "integer", "minimum": 500, "maximum": 20000},
                        },
                        "required": ["url"],
                    },
                    handler=self._fetch_web_page,
                ),
                Tool(
                    name="shell_command",
                    description="Run a restricted read-only shell command. Only curl/curl.exe requests are allowed.",
                    parameters={
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"],
                    },
                    handler=self._shell_command,
                ),
                Tool(
                    name="conversation_digest",
                    description="Return recent conversation messages for review, TODO extraction, or inspiration organization.",
                    parameters={
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                    },
                    handler=self._conversation_digest,
                ),
            )
        }

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict, context: ToolContext) -> str:
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
        return tool.handler(arguments, context)

    def _activate_skill(self, arguments: dict, context: ToolContext) -> str:
        skill_name = str(arguments.get("name", ""))
        skill = self.skill_registry.get(skill_name)
        if not skill:
            return json.dumps({"error": f"Skill not found: {skill_name}"}, ensure_ascii=False)
        return skill.content

    def _fetch_web_page(self, arguments: dict, context: ToolContext) -> str:
        url = str(arguments.get("url", ""))
        max_chars = int(arguments.get("max_chars") or 10000)
        parsed = parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return json.dumps({"error": "Only http(s) URLs are supported."}, ensure_ascii=False)

        try:
            response = self.http_client.request_bytes(
                url,
                headers={"User-Agent": "ShinobuChat/agent"},
                timeout=settings.ai_request_timeout_seconds,
            )
        except HttpClientError as exc:
            return json.dumps({"error": f"Fetch failed: {exc}"}, ensure_ascii=False)

        text = response.body[: min(max_chars * 4, 100_000)].decode("utf-8", errors="replace")
        return text[:max_chars]

    def _shell_command(self, arguments: dict, context: ToolContext) -> str:
        command = str(arguments.get("command", ""))
        if any(token in command for token in ("|", "&", ";", ">", "<", "`", "$(")):
            return "Rejected: shell control operators are not allowed."

        try:
            parts = shlex.split(command, posix=False)
        except ValueError as exc:
            return f"Rejected: could not parse command: {exc}"

        if not parts or parts[0].lower() not in {"curl", "curl.exe"}:
            return "Rejected: only curl/curl.exe commands are allowed."

        completed = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=min(settings.ai_request_timeout_seconds, 30),
            check=False,
        )
        output = (completed.stdout or completed.stderr or "").strip()
        return output[:12000] or f"Command exited with code {completed.returncode} and no output."

    def _conversation_digest(self, arguments: dict, context: ToolContext) -> str:
        limit = int(arguments.get("limit") or 20)
        items = context.history[-limit:]
        lines = [
            f"{message.created_at.isoformat()} {message.role}: {message.content}"
            for message in items
        ]
        return "\n".join(lines)
