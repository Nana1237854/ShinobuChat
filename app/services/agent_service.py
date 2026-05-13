from __future__ import annotations

import json
import shlex
import subprocess
from urllib import error, parse, request

from app.core.config import settings
from app.models.message import Message
from app.schemas.message import MessageRole
from app.services.skill_service import Skill, SkillRegistry


class AgentService:
    def __init__(self, skill_registry: SkillRegistry):
        self.skill_registry = skill_registry

    def build_messages(
        self,
        content: str,
        history: list[Message],
        activated_skills: list[Skill],
    ) -> list[dict]:
        skill_blocks = "\n\n".join(
            f"<skill name=\"{skill.name}\">\n{skill.content}\n</skill>"
            for skill in activated_skills
        )
        system = (
            "你是 ShinobuChat 的 Agent Core。你不只是聊天，要在需要时使用工具完成任务。"
            "技能系统遵循 AgentSkills/EchoBot 风格：先激活匹配的 SKILL.md，把其中工作流当作当前任务说明，"
            "再调用通用工具获取事实或执行只读动作，最后用中文给用户一个清楚、简短、可用的结果。\n\n"
            "可用技能目录：\n"
            f"{self.skill_registry.render_catalog() or '- 当前没有安装技能'}\n\n"
            "规则：\n"
            "1. 已注入的技能优先执行；需要其他技能时调用 activate_skill。\n"
            "2. 工具结果要被你解释成自然语言，不要原样倾倒长日志。\n"
            "3. shell_command 只用于 SKILL.md 明确要求的只读 curl 请求。\n"
            "4. 如果技能需要当前后端拿不到的输入，例如真实屏幕截图，先说明缺少什么，再给下一步。\n"
        )
        if skill_blocks:
            system += f"\n已激活技能：\n{skill_blocks}\n"

        messages: list[dict] = [{"role": MessageRole.SYSTEM.value, "content": system}]
        for message in history[-16:]:
            if message.role in {MessageRole.USER.value, MessageRole.ASSISTANT.value}:
                messages.append({"role": message.role, "content": message.content})
        messages.append({"role": MessageRole.USER.value, "content": content})
        return messages

    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "activate_skill",
                    "description": "Load a local SKILL.md by skill name and return its instructions.",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_web_page",
                    "description": "Fetch a webpage and return text content for summarization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "max_chars": {"type": "integer", "minimum": 500, "maximum": 20000},
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shell_command",
                    "description": "Run a restricted read-only shell command. Only curl/curl.exe requests are allowed.",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "conversation_digest",
                    "description": "Return recent conversation messages for review, TODO extraction, or inspiration organization.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                    },
                },
            },
        ]

    def execute_tool(self, name: str, arguments: dict, history: list[Message]) -> str:
        if name == "activate_skill":
            skill_name = str(arguments.get("name", ""))
            skill = self.skill_registry.get(skill_name)
            if not skill:
                return json.dumps({"error": f"Skill not found: {skill_name}"}, ensure_ascii=False)
            return skill.content
        if name == "fetch_web_page":
            return self._fetch_web_page(
                str(arguments.get("url", "")),
                int(arguments.get("max_chars") or 10000),
            )
        if name == "shell_command":
            return self._shell_command(str(arguments.get("command", "")))
        if name == "conversation_digest":
            limit = int(arguments.get("limit") or 20)
            return self._conversation_digest(history, limit)
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)

    def _fetch_web_page(self, url: str, max_chars: int) -> str:
        parsed = parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return json.dumps({"error": "Only http(s) URLs are supported."}, ensure_ascii=False)

        req = request.Request(url, headers={"User-Agent": "ShinobuChat/agent"})
        try:
            with request.urlopen(req, timeout=settings.ai_request_timeout_seconds) as resp:
                raw = resp.read(min(max_chars * 4, 100_000))
        except (error.HTTPError, error.URLError, TimeoutError) as exc:
            return json.dumps({"error": f"Fetch failed: {exc}"}, ensure_ascii=False)

        text = raw.decode("utf-8", errors="replace")
        return text[:max_chars]

    def _shell_command(self, command: str) -> str:
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

    def _conversation_digest(self, history: list[Message], limit: int) -> str:
        items = history[-limit:]
        lines = [
            f"{message.created_at.isoformat()} {message.role}: {message.content}"
            for message in items
        ]
        return "\n".join(lines)
