"""Context intent resolver.

LLM-driven intent resolution that uses the full ContextPack
(recent messages, summary, memories, diary, pending intent, tools,
local apps) to determine the user's real intent.

v1: only resolve open_local_app / clarify / chat / none.
Other actions (search_web, browser_open, etc.) are reserved.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.exceptions import UpstreamServiceError
from app.schemas.context_intent import ContextIntentResult, ContextPack

logger = logging.getLogger("shinobu.context_intent_resolver")

_VALID_ACTIONS = {"open_local_app", "clarify", "chat", "none"}
_ALLOWED_INTENT_TYPES = {
    "open_music", "open_browser", "open_ide", "open_file_explorer",
    "open_terminal", "open_note_app", "open_design_app", "open_chat_app", "open_custom",
}

_SYSTEM_PROMPT = """你是 ShinobuChat 的上下文意图解析器。你的任务是根据当前用户输入、最近对话、对话摘要、相关记忆、日记摘要、待承接意图、可用工具和用户已配置本地应用，解析用户当前真实意图。

你只负责判断意图，不负责执行。你不能声称已经打开应用。你不能编造用户没有配置的本地应用。

规则：
1. 你只能从"用户已配置本地应用"中选择 app_key 和 app_name。不能自创应用名。
2. 如果用户只是表达情绪、闲聊、假设、否定、反问（"不想""算了""不用了""别"），不要输出 open_local_app。
3. 如果用户短回复（"是的""好""听听看""对啊""可以""行""嗯""ok""yes"），必须结合"待承接意图"和"最近对话"判断是否应承接上一轮的动作。如果上一轮 AI 问了"要不要在 XX 应用听歌"，pending_conversation_intent.kind=open_music_app，用户说"是的"，就应该输出 open_local_app。
4. 如果用户短回复但上下文没有待承接意图（没有 pending_conversation_intent，或最近对话没有 AI 询问），则输出 chat。
5. confidence < 0.75 时，必须输出 chat 或 clarify，不能输出 open_local_app。
6. 如果用户想让 AI 做某件事但信息不足（多个应用可选、没有默认应用），输出 clarify 并给出 clarification_question。
7. 如果用户只是在聊天、评价、讨论，没有工具执行意图，输出 action=chat。
8. action=clarify 时，should_save_pending_intent=true 并填入 pending_intent。
9. 不要输出解释、Markdown、代码块。只输出纯 JSON。"""


class ContextIntentResolver:
    """Resolve user intent from a structured ContextPack using LLM.

    Can be a lru_cache singleton — holds only ai_client, no db session.
    """

    def __init__(self, ai_client=None):
        self.ai_client = ai_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(
        self,
        *,
        user_id,
        conversation_id,
        user_text: str,
        context_pack: ContextPack,
        runtime_config: dict[str, Any] | None = None,
    ) -> ContextIntentResult:
        """Resolve intent from context pack via LLM.

        Returns a validated ContextIntentResult. Never throws —
        falls back to action="chat" on any failure.
        """
        try:
            raw_json = self._call_llm(user_text, context_pack, runtime_config)
            parsed = self._parse_json(raw_json)
            validated = self._validate(parsed)
            return validated
        except UpstreamServiceError:
            logger.warning("Context intent LLM call failed (upstream), falling back to chat")
        except Exception:
            logger.warning("Context intent resolution failed", exc_info=True)
        return ContextIntentResult(action="chat", reason="resolution_failed")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        user_text: str,
        context_pack: ContextPack,
        runtime_config: dict[str, Any] | None,
    ) -> str:
        if not self.ai_client:
            raise RuntimeError("No AI client available")

        user_prompt = self._build_user_prompt(user_text, context_pack)

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        response = self.ai_client.complete_chat(
            messages=messages,
            max_tokens=300,
            runtime_config=runtime_config,
        )
        content = (response.get("content") or "").strip()
        if not content:
            raise UpstreamServiceError("LLM returned empty response for intent resolution")
        return content

    @staticmethod
    def _build_user_prompt(user_text: str, pack: ContextPack) -> str:
        lines: list[str] = []

        lines.append(f"当前用户输入：{user_text}")
        lines.append("")

        lines.append("最近对话：")
        if pack.recent_messages:
            for m in pack.recent_messages[-6:]:
                role = "用户" if m.get("role") == "user" else "AI"
                lines.append(f"  [{role}] {m.get('content', '')[:200]}")
        else:
            lines.append("  （无）")
        lines.append("")

        lines.append(f"当前对话摘要：{pack.conversation_summary or '（无）'}")
        lines.append("")

        lines.append("相关记忆：")
        if pack.relevant_memories:
            for m in pack.relevant_memories:
                lines.append(f"  - {m.get('content', '')}")
        else:
            lines.append("  （无）")
        lines.append("")

        lines.append("最近日记摘要：")
        if pack.diary_summaries:
            for d in pack.diary_summaries:
                lines.append(f"  - [{d.get('date', '?')}] {d.get('summary', '')}")
        else:
            lines.append("  （无）")
        lines.append("")

        lines.append("待承接意图：")
        pci = pack.pending_conversation_intent
        if pci:
            lines.append(f"  kind={pci.get('kind', '')}")
            lines.append(f"  intent_type={pci.get('intent_type', '')}")
            lines.append(f"  app_name={pci.get('app_name', '')}")
            lines.append(f"  query={pci.get('query', '')}")
        else:
            lines.append("  （无）")
        lines.append("")

        lines.append("可用工具：")
        for t in pack.available_tools:
            lines.append(f"  - {t.get('name', '')}: {t.get('description', '')}")
        lines.append("")

        lines.append("用户已配置本地应用：")
        if pack.available_local_apps:
            for a in pack.available_local_apps:
                kw = ", ".join(a.get("keywords", [])[:5])
                default = " [默认]" if a.get("is_default_for_intent") else ""
                lines.append(
                    f"  - app_key={a.get('app_key')}, "
                    f"display_name={a.get('display_name')}, "
                    f"intent_type={a.get('intent_type')}, "
                    f"keywords=[{kw}]{default}"
                )
        else:
            lines.append("  （无）")
        lines.append("")

        lines.append(f"当前情景模式：{pack.conversation_mode}")
        lines.append("")
        lines.append("请输出结构化 JSON（只输出 JSON，不要解释）。")

        return "\n".join(lines)

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        """Robust JSON extraction from LLM output."""
        text = raw.strip()
        # Remove markdown code fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting first JSON object
        match = re.search(r"\{[^{}]*?\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Try a more aggressive approach for nested JSON
        brace_count = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == "{":
                if brace_count == 0:
                    start = i
                brace_count += 1
            elif ch == "}":
                brace_count -= 1
                if brace_count == 0 and start >= 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        start = -1
                        continue

        raise ValueError(f"Failed to parse JSON from LLM output: {raw[:200]}")

    @staticmethod
    def _validate(raw: dict[str, Any]) -> ContextIntentResult:
        """Validate and sanitize the parsed LLM output."""
        action = raw.get("action", "chat")
        if action not in _VALID_ACTIONS:
            action = "chat"

        intent_type = raw.get("intent_type")
        if intent_type and intent_type not in _ALLOWED_INTENT_TYPES:
            intent_type = None

        confidence = raw.get("confidence", 0.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        # If action is open_local_app but confidence too low, demote
        if action == "open_local_app" and confidence < 0.75:
            action = "chat"

        result = ContextIntentResult(
            action=action,
            intent_type=intent_type,
            app_name=raw.get("app_name"),
            app_key=raw.get("app_key"),
            query=raw.get("query"),
            confidence=confidence,
            requires_clarification=bool(raw.get("requires_clarification", False)),
            clarification_question=raw.get("clarification_question"),
            should_save_pending_intent=bool(raw.get("should_save_pending_intent", False)),
            pending_intent=raw.get("pending_intent"),
            reason=raw.get("reason"),
        )
        return result
