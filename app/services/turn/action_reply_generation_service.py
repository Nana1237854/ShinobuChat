"""Action reply generation service.

Generates natural, character-appropriate Chinese replies for local-app
action results (opened / requires_confirmation / requires_selection /
not_configured / failed).

Supports:
- LLM-driven reply generation with safety boundaries
- Memory / diary / conversation context injection
- Per-user personalization config (action_reply_personalization_enabled, etc.)
- Fallback to hardcoded templates on any error
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.exceptions import UpstreamServiceError

logger = logging.getLogger("shinobu.action_reply")


# ---------------------------------------------------------------------------
# Context container
# ---------------------------------------------------------------------------

@dataclass
class ActionReplyMemoryContext:
    relevant_memories: list[str]
    recent_diary_summaries: list[str]
    recent_conversation_hints: list[str]


# ---------------------------------------------------------------------------
# Keyword fallback for memory retrieval (when embedding is unavailable)
# ---------------------------------------------------------------------------

_INTENT_KEYWORD_MAP: dict[str, list[str]] = {
    "open_music": ["音乐", "歌", "听歌", "歌单", "网易云", "情绪", "夜跑", "学习", "放松", "通勤", "睡前"],
    "open_ide": ["代码", "编程", "IDE", "VS Code", "Android Studio", "项目", "开发", "学习", "工作", "Bug"],
    "open_browser": ["搜索", "网页", "资料", "查找", "浏览器", "学习", "新闻"],
    "open_file_explorer": ["文件", "文件夹", "项目", "资料", "整理"],
}


# ---------------------------------------------------------------------------
# Fallback templates — used when AI is unavailable
# ---------------------------------------------------------------------------

def _fallback_reply(
    status: str,
    display_name: str | None = None,
    intent_type: str | None = None,
    candidates: list[dict] | None = None,
    selected_by: str | None = None,
    selection_message: str | None = None,
) -> str:
    """Return a safe, hardcoded reply for every *status*."""
    name = display_name or intent_type or "这个应用"
    candidates = candidates or []

    if status == "opened":
        return f"[happy]已经帮你打开 {name} 啦～想接下来做点什么呢？"

    if status == "requires_confirmation":
        prefix = f"{selection_message} " if selection_message else ""
        return f"[thinking]{prefix}{name} 需要确认才能打开哦，请确认一下～"

    if status == "requires_selection":
        candidate_names = "、".join(
            str(c.get("display_name") or c.get("app_key"))
            for c in candidates[:4]
            if c
        )
        if candidate_names:
            return (
                f"[thinking]我找到多个匹配的应用：{candidate_names}。"
                f"你可以设置一个默认应用，或者直接告诉我要打开哪个～"
            )
        return (
            "[thinking]我找到多个匹配的应用，"
            "请在设置里选择默认应用，或者直接告诉我要打开哪个～"
        )

    if status == "not_configured":
        return f"[neutral]我还没找到 {name} 的本地应用配置呢，去设置里配置一下吧～"

    if status == "forbidden":
        return "[neutral]本地应用功能还没有开启呢，先去设置里打开吧～"

    return f"[neutral]抱歉，打开 {name} 失败了，可能是路径有问题，去检查一下吧～"


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_bullets(items: list[str] | None, max_items: int = 5) -> str:
    if not items:
        return "（无）"
    return "\n".join(f"  - {item[:120]}" for item in items[:max_items])


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ActionReplyGenerationService:
    """Generate natural companion-style replies for local-app actions.

    Delegates to an AIClient when available and personalization is enabled;
    falls back to hardcoded templates on any error.
    """

    def __init__(
        self,
        *,
        ai_client=None,
        config_service=None,
        memory_service=None,
        diary_service=None,
        mode_service=None,
    ):
        self.ai_client = ai_client
        self.config_service = config_service
        self.memory_service = memory_service
        self.diary_service = diary_service
        self.mode_service = mode_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        *,
        user_id,
        user_text: str = "",
        status: str = "failed",
        action_type: str = "open_local_app",
        intent_type: str | None = None,
        app_key: str | None = None,
        display_name: str | None = None,
        result_message: str | None = None,
        conversation_mode: str = "companion",
        selected_by: str | None = None,
        selection_message: str | None = None,
        candidates: list[dict] | None = None,
        requires_confirmation: bool = False,
        error_detail: str | None = None,
    ) -> str:
        """Return a companion-style reply for the given action result.

        Never throws — always returns a usable reply string, falling back
        to templates when generation fails.
        """
        # Check personalization config
        if self.config_service:
            try:
                enabled = self.config_service.get_effective_value(
                    user_id, "action_reply_personalization_enabled"
                )
                if enabled is False:
                    return _fallback_reply(
                        status=status,
                        display_name=display_name,
                        intent_type=intent_type,
                        candidates=candidates,
                        selected_by=selected_by,
                        selection_message=selection_message,
                    )
            except Exception:
                pass

        if not self.ai_client:
            return _fallback_reply(
                status=status,
                display_name=display_name,
                intent_type=intent_type,
                candidates=candidates,
                selected_by=selected_by,
                selection_message=selection_message,
            )

        # Collect memory context
        memory_ctx = self._collect_memory_context(
            user_id=user_id,
            user_text=user_text,
            intent_type=intent_type,
            display_name=display_name,
        )

        try:
            reply = self._generate_with_ai(
                user_id=user_id,
                user_text=user_text,
                status=status,
                action_type=action_type,
                intent_type=intent_type,
                app_key=app_key,
                display_name=display_name,
                result_message=result_message,
                conversation_mode=conversation_mode,
                selected_by=selected_by,
                selection_message=selection_message,
                candidates=candidates,
                requires_confirmation=requires_confirmation,
                error_detail=error_detail,
                memory_ctx=memory_ctx,
            )
            if reply and reply.strip():
                return reply
        except UpstreamServiceError:
            logger.warning(
                "Action reply generation failed due to upstream AI error (status=%s), falling back to template",
                status,
                exc_info=True,
            )
        except Exception:
            logger.warning(
                "AI reply generation failed for status=%s, falling back to template",
                status,
                exc_info=True,
            )

        return _fallback_reply(
            status=status,
            display_name=display_name,
            intent_type=intent_type,
            candidates=candidates,
            selected_by=selected_by,
            selection_message=selection_message,
        )

    # ------------------------------------------------------------------
    # Memory / diary context collection
    # ------------------------------------------------------------------

    def _collect_memory_context(
        self,
        user_id: UUID,
        user_text: str = "",
        intent_type: str | None = None,
        display_name: str | None = None,
    ) -> ActionReplyMemoryContext:
        """Collect relevant memories, diary summaries and conversation hints."""
        use_memory = True
        use_diary = True
        if self.config_service:
            try:
                use_memory = self.config_service.get_effective_value(user_id, "action_reply_use_memory")
                use_diary = self.config_service.get_effective_value(user_id, "action_reply_use_diary")
                if use_memory is None:
                    use_memory = True
                if use_diary is None:
                    use_diary = True
            except Exception:
                pass

        query = f"{user_text} {intent_type or ''} {display_name or ''}".strip()

        memories: list[str] = []
        if use_memory and self.memory_service:
            try:
                memories = self._retrieve_memories(user_id, query, intent_type)
            except Exception:
                logger.debug("Memory retrieval failed for action reply", exc_info=True)

        diaries: list[str] = []
        if use_diary and self.diary_service:
            try:
                diaries = self._retrieve_diary_summaries(user_id, query)
            except Exception:
                logger.debug("Diary retrieval failed for action reply", exc_info=True)

        conversation_hints: list[str] = []
        # Conversation hints are best-effort and only used if available

        return ActionReplyMemoryContext(
            relevant_memories=memories[:3],
            recent_diary_summaries=diaries[:2],
            recent_conversation_hints=conversation_hints[:3],
        )

    def _retrieve_memories(
        self, user_id: UUID, query: str, intent_type: str | None
    ) -> list[str]:
        """Retrieve relevant memory content strings."""
        keywords = _INTENT_KEYWORD_MAP.get(intent_type or "", [])
        all_keywords = list(set(keywords + [query]))

        try:
            results = self.memory_service.search_memories(user_id, query=all_keywords[0])
            return [
                (r.content[:80] + "…" if len(r.content) > 80 else r.content)
                for r in (results or [])[:3]
                if r and r.content
            ]
        except Exception:
            return []

    def _retrieve_diary_summaries(
        self, user_id: UUID, query: str
    ) -> list[str]:
        """Retrieve recent diary summaries."""
        try:
            from datetime import date, timedelta

            today = date.today()
            start = today - timedelta(days=30)
            diaries = self.diary_service.list_diaries_in_range(user_id, start, today)
            summaries: list[str] = []
            for d in (diaries or [])[:5]:
                summary = getattr(d, "summary", None) or getattr(d, "title", None)
                if summary:
                    text = str(summary)[:80]
                    summaries.append(text)
            return summaries[:2]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # AI generation
    # ------------------------------------------------------------------

    def _generate_with_ai(self, **kwargs) -> str | None:
        """Call the AI model to produce a natural-language reply."""
        messages = [
            {"role": "system", "content": self._system_prompt(kwargs.get("user_id"))},
            {"role": "user", "content": self._user_prompt(kwargs)},
        ]

        # Resolve runtime config
        runtime_config = None
        reply_model = None
        reply_max_tokens = 200
        reply_temperature = 0.7

        if self.config_service:
            uid = kwargs.get("user_id")
            try:
                runtime_config = self.config_service.resolve_runtime(uid)
                reply_model = self.config_service.get_effective_value(uid, "action_reply_model")
                reply_max_tokens = self.config_service.get_effective_value(uid, "action_reply_max_tokens") or 200
                reply_temperature = self.config_service.get_effective_value(uid, "action_reply_temperature") or 0.7
            except Exception:
                pass

        # If reply_model is specified, override in runtime_config
        if reply_model and runtime_config is not None:
            runtime_config = dict(runtime_config)
            runtime_config["ai_model"] = reply_model

        response = self.ai_client.complete_chat(
            messages=messages,
            max_tokens=int(reply_max_tokens),
            runtime_config=runtime_config,
        )
        content = (response.get("content") or "").strip()
        return content or None

    @staticmethod
    def _system_prompt(user_id) -> str:
        return (
            "你是 ShinobuChat 中的虚拟伴侣 Shinobu。\n"
            "你要把本地应用操作结果转成自然、温柔、有陪伴感的中文回复。\n"
            "\n"
            "你可以参考提供的记忆和日记摘要，让回复更贴近用户习惯。\n"
            "但你必须遵守事实边界：\n"
            "\n"
            "1. 你不能改变操作事实。\n"
            "2. 如果 status=opened，才可以说已经打开。\n"
            "3. 如果 status=requires_confirmation，只能说需要用户确认，不能说已经打开。\n"
            "4. 如果 status=requires_selection，只能说明有多个应用，需要设置默认或让用户明确指定。\n"
            "5. 如果 status=not_configured，只能说明没有找到已配置的应用。\n"
            "6. 如果 status=failed，只能说明打开失败。\n"
            "7. 只能引用下方提供的记忆和日记摘要，不能编造用户偏好。\n"
            "8. 不要输出 JSON。\n"
            "9. 不要输出技术字段名，例如 app_key、intent_type，除非用户正在排查配置。\n"
            "10. 回复控制在 1~3 句话。\n"
            "11. 保持 Shinobu 的陪伴感，可以轻微俏皮，但不要过度卖萌。\n"
            "12. 如果 selected_by=default_for_intent 且 selection_message 提到默认应用，"
            "要在回复中说明选择了默认应用。"
        )

    @staticmethod
    def _user_prompt(kwargs: dict) -> str:
        candidates = kwargs.get("candidates") or []
        candidate_names = [
            c.get("display_name", c.get("app_key", "?")) for c in candidates[:5]
        ]
        memory_ctx: ActionReplyMemoryContext | None = kwargs.get("memory_ctx")

        lines = [
            f"用户原话：{kwargs.get('user_text') or '（未提供）'}",
            "",
            "动作事实（不可改变）：",
            f"  status={kwargs.get('status')}",
            f"  action_type={kwargs.get('action_type')}",
            f"  intent_type={kwargs.get('intent_type') or '-'}",
            f"  display_name={kwargs.get('display_name') or '-'}",
            f"  app_key={kwargs.get('app_key') or '-'}",
            f"  result_message={kwargs.get('result_message') or '-'}",
            f"  selected_by={kwargs.get('selected_by') or '-'}",
            f"  selection_message={kwargs.get('selection_message') or '-'}",
            f"  requires_confirmation={kwargs.get('requires_confirmation')}",
            f"  error_detail={kwargs.get('error_detail') or '-'}",
            f"  candidates={candidate_names if candidate_names else '-'}",
            "",
            "相关记忆：",
            _format_bullets(
                memory_ctx.relevant_memories if memory_ctx else None
            ),
            "",
            "最近日记摘要：",
            _format_bullets(
                memory_ctx.recent_diary_summaries if memory_ctx else None
            ),
            "",
            "最近对话提示：",
            _format_bullets(
                memory_ctx.recent_conversation_hints if memory_ctx else None
            ),
            "",
            "请生成一段面向用户的自然中文回复。",
        ]
        return "\n".join(lines)
