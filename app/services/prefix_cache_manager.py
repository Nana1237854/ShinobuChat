from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.core.config import settings
from app.models.message import Message
from app.schemas.message import MessageRole
from app.services.constitution_service import ConstitutionService

logger = logging.getLogger("shinobu.prefix_cache")


@dataclass(frozen=True)
class PromptBundle:
    pinned_prefix: str
    pinned_prefix_sha: str
    append_log: list[dict[str, str]]
    turn_scratch: str
    messages: list[dict[str, str]]


class PrefixCacheManager:
    """Three-zone prompt builder: PinnedPrefix, AppendLog, TurnScratch.

    Zone 1 (PinnedPrefix): system prompt, constitution, character card,
        tool directory, skill directory — byte-stable, SHA-256 frozen.
    Zone 2 (AppendLog): conversation history — append-only, never rewrite.
    Zone 3 (TurnScratch): current user message, retrieved memories,
        tool results, route decision — cleared every turn.
    """

    def __init__(
        self,
        constitution_path: Path | None = None,
        character_path: Path | None = None,
        constitution_service: ConstitutionService | None = None,
    ):
        root = Path(__file__).resolve().parents[2]
        self.constitution_path = constitution_path or root / "constitution.json"
        self.character_path = character_path or settings.characters_dir / "shinobu.yaml"
        self.constitution_service = constitution_service or ConstitutionService(self.constitution_path)

        self._frozen_sha: str | None = None
        self._frozen_system_text: str | None = None
        self._frozen_tools_json: str | None = None
        self._frozen_skill_catalog: str | None = None
        self._frozen_pinned_prefix: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def freeze(self, system_text: str, tools: list[dict], skill_catalog: str = "") -> str:
        """Freeze Zone 1 (PinnedPrefix) and return its SHA-256 digest.

        Args:
            system_text: base system prompt (already includes role/tone instructions).
            tools: list of tool definition dicts in OpenAI function-calling shape.
            skill_catalog: rendered skill catalog text (names + descriptions only).

        Returns:
            Hex-encoded SHA-256 of the full pinned prefix.
        """
        tools_json = json.dumps(tools, sort_keys=True, ensure_ascii=False)

        changed = False
        if self._frozen_system_text is not None:
            if self._frozen_system_text != system_text:
                changed = True
                logger.info("Prefix refrozen: system_text changed")
            elif self._frozen_tools_json != tools_json:
                changed = True
                logger.info("Prefix refrozen: tools changed")
            elif self._frozen_skill_catalog != skill_catalog:
                changed = True
                logger.info("Prefix refrozen: skill_catalog changed")

        self._frozen_system_text = system_text
        self._frozen_tools_json = tools_json
        self._frozen_skill_catalog = skill_catalog

        tool_catalog = self._format_tools(tools)
        pinned = self._pinned_prefix(
            base_system=system_text,
            skill_catalog=skill_catalog,
            tool_catalog=tool_catalog,
        )
        new_sha = hashlib.sha256(pinned.encode("utf-8")).hexdigest()

        if self._frozen_sha is None:
            logger.info("Prefix frozen: sha=%s", new_sha[:16])
        elif changed:
            logger.info(
                "Prefix refrozen: old_sha=%s new_sha=%s",
                self._frozen_sha[:16],
                new_sha[:16],
            )
        self._frozen_sha = new_sha
        self._frozen_pinned_prefix = pinned
        return self._frozen_sha

    def verify(self, current_system: str, current_tools: list[dict]) -> bool:
        """Check whether *current_system* + *current_tools* still match the frozen prefix.

        Returns ``False`` and logs a warning when a mismatch is detected.
        """
        if self._frozen_sha is None:
            logger.warning("verify called before freeze — no frozen prefix to compare")
            return False

        tools_json = json.dumps(current_tools, sort_keys=True, ensure_ascii=False)
        system_ok = current_system == self._frozen_system_text
        tools_ok = tools_json == self._frozen_tools_json

        if not system_ok or not tools_ok:
            reasons = []
            if not system_ok:
                reasons.append("system_text changed")
            if not tools_ok:
                reasons.append("tools changed")
            logger.warning("Prefix mismatch detected: %s", ", ".join(reasons))
            return False

        # Verify SHA hasn't been corrupted
        pinned = self._pinned_prefix(
            base_system=current_system,
            skill_catalog=self._frozen_skill_catalog or "",
            tool_catalog=self._format_tools(current_tools),
        )
        current_sha = hashlib.sha256(pinned.encode("utf-8")).hexdigest()
        if current_sha != self._frozen_sha:
            logger.warning(
                "Prefix SHA mismatch (possible corruption): frozen=%s current=%s",
                self._frozen_sha[:16],
                current_sha[:16],
            )
            return False

        return True

    def build_messages(self, history: list[dict], turn_scratch: dict) -> list[dict]:
        """Build the full three-zone message list for an LLM call.

        Args:
            history: Zone 2 — list of ``{"role": ..., "content": ...}`` dicts,
                     already filtered to user/assistant roles.
            turn_scratch: Zone 3 data. Keys:
                - ``user_message`` (str, required): current user input.
                - ``memory_context`` (list[str], optional): retrieved memories.
                - ``tool_results`` (list[str], optional): tool call results this turn.
                - ``route_decision`` (str, optional): router decision summary.
                - ``activated_skills`` (list[tuple[str, str]], optional):
                  (name, content) pairs for activated skills.

        Returns:
            List of message dicts ready for the LLM API.
        """
        if self._frozen_sha is None:
            pinned_prefix = self._pinned_prefix(
                base_system="",
                skill_catalog=self._frozen_skill_catalog or "",
                tool_catalog="",
            )
            self._frozen_sha = hashlib.sha256(pinned_prefix.encode("utf-8")).hexdigest()
            self._frozen_pinned_prefix = pinned_prefix
            logger.warning("build_messages called before freeze — using empty pinned prefix")

        pinned_prefix = self._frozen_pinned_prefix or ""

        messages: list[dict[str, str]] = [
            {"role": MessageRole.SYSTEM.value, "content": pinned_prefix}
        ]
        # Zone 2: AppendLog — append only, never mutate history entries
        for entry in history:
            role = entry.get("role", "")
            if role in (MessageRole.USER.value, MessageRole.ASSISTANT.value):
                messages.append({"role": role, "content": entry.get("content", "")})

        # Zone 3: TurnScratch — ephemeral, cleared every turn
        scratch_text = self._build_turn_scratch(turn_scratch)
        if scratch_text:
            messages.append({"role": MessageRole.SYSTEM.value, "content": scratch_text})

        user_message = turn_scratch.get("user_message", "")
        messages.append({"role": MessageRole.USER.value, "content": user_message})

        return messages

    # ------------------------------------------------------------------
    # Legacy API — kept for backward compatibility
    # ------------------------------------------------------------------

    def build(
        self,
        *,
        base_system: str,
        history: list[Message],
        user_message: str,
        skill_catalog: str = "",
        tool_catalog: str = "",
        memory_context: list[str] | None = None,
        activated_skills: list[tuple[str, str]] | None = None,
        history_limit: int = 16,
    ) -> PromptBundle:
        pinned_prefix = self._pinned_prefix(
            base_system=base_system,
            skill_catalog=skill_catalog,
            tool_catalog=tool_catalog,
        )
        pinned_sha = hashlib.sha256(pinned_prefix.encode("utf-8")).hexdigest()

        # Track SHA for freeze/verify compatibility
        if self._frozen_sha is None:
            logger.info("Prefix frozen (implicit via build): sha=%s", pinned_sha[:16])
        elif pinned_sha != self._frozen_sha:
            logger.info(
                "Prefix changed (via build): old_sha=%s new_sha=%s",
                self._frozen_sha[:16],
                pinned_sha[:16],
            )
        self._frozen_sha = pinned_sha
        self._frozen_system_text = base_system
        self._frozen_pinned_prefix = pinned_prefix

        append_log = [
            {"role": message.role, "content": message.content}
            for message in history[-history_limit:]
            if message.role in {MessageRole.USER.value, MessageRole.ASSISTANT.value}
        ]
        scratch_parts: list[str] = []
        if memory_context:
            scratch_parts.append(
                "【本轮检索到的长期记忆】\n"
                + "\n".join(f"- {item}" for item in memory_context)
                + "\n仅在与当前请求相关时自然参考。"
            )
        if activated_skills:
            scratch_parts.append(
                "【本轮已激活 Skill】\n"
                + "\n\n".join(
                    f"<skill name=\"{name}\">\n{content}\n</skill>"
                    for name, content in activated_skills
                )
            )
        turn_scratch = "\n\n".join(scratch_parts)
        messages: list[dict[str, str]] = [
            {"role": MessageRole.SYSTEM.value, "content": pinned_prefix}
        ]
        messages.extend(append_log)
        if turn_scratch:
            messages.append({"role": MessageRole.SYSTEM.value, "content": turn_scratch})
        messages.append({"role": MessageRole.USER.value, "content": user_message})
        return PromptBundle(
            pinned_prefix=pinned_prefix,
            pinned_prefix_sha=pinned_sha,
            append_log=append_log,
            turn_scratch=turn_scratch,
            messages=messages,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pinned_prefix(self, *, base_system: str, skill_catalog: str, tool_catalog: str) -> str:
        sections = [
            "【System】\n" + base_system.strip(),
            "【Constitution】\n" + self._constitution_summary(),
            "【Character card】\n" + self._character_summary(),
            "【Registered tools】\n" + (tool_catalog.strip() or "- none"),
            "【Available Skills】\n" + (skill_catalog.strip() or "- none"),
        ]
        return "\n\n".join(sections).strip() + "\n"

    def _constitution_summary(self) -> str:
        return self.constitution_service.build_prompt_section()

    def _character_summary(self) -> str:
        try:
            payload = yaml.safe_load(self.character_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return "name: Shinobu"
        keep = {
            key: payload.get(key)
            for key in ("name", "persona", "tone", "system_prompt_extra")
            if payload.get(key) not in (None, "", [], {})
        }
        return yaml.safe_dump(keep, allow_unicode=True, sort_keys=True).strip()

    @staticmethod
    def _format_tools(tools: list[dict]) -> str:
        if not tools:
            return ""
        sorted_tools = sorted(tools, key=lambda t: t.get("function", {}).get("name", ""))
        lines: list[str] = []
        for tool in sorted_tools:
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            params = func.get("parameters", {})
            required = params.get("required", [])
            lines.append(f"- {name}: {desc}")
            if required:
                lines.append(f"  required: {', '.join(required)}")
        return "\n".join(lines)

    @staticmethod
    def _build_turn_scratch(turn_scratch: dict) -> str:
        parts: list[str] = []
        memory_context = turn_scratch.get("memory_context")
        if memory_context:
            parts.append(
                "【本轮检索到的长期记忆】\n"
                + "\n".join(f"- {item}" for item in memory_context)
                + "\n仅在与当前请求相关时自然参考。"
            )
        tool_results = turn_scratch.get("tool_results")
        if tool_results:
            parts.append(
                "【本轮工具结果】\n" + "\n".join(f"- {r}" for r in tool_results)
            )
        route_decision = turn_scratch.get("route_decision")
        if route_decision:
            parts.append(f"【本轮路由决策】\n{route_decision}")
        activated_skills = turn_scratch.get("activated_skills")
        if activated_skills:
            parts.append(
                "【本轮已激活 Skill】\n"
                + "\n\n".join(
                    f"<skill name=\"{name}\">\n{content}\n</skill>"
                    for name, content in activated_skills
                )
            )
        return "\n\n".join(parts)
