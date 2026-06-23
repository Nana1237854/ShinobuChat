from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError, UpstreamServiceError
from app.core.time import local_now
from app.models.conversation import Conversation
from app.models.diary import Diary
from app.models.message import Message
from app.models.todo import Todo
from app.models.user_goal import UserGoal
from app.schemas.diary import DiaryDetail, DiaryGenerateRequest, DiaryGenerateResponse, DiaryOut

logger = logging.getLogger(__name__)

DIARY_PROMPT = """你是一个 AI 陪伴角色 Shinobu。请根据提供的今日数据，用第一人称写一篇当天的日记。

日记格式（请返回严格 JSON）：
{
  "title": "日记标题（10字以内）",
  "summary": "一句话总结今天（30字以内）",
  "content": "日记正文（200-500字），按以下结构：\n今日互动、任务与目标、情绪观察、今日小记",
  "mood": "happy/worried/tired/neutral/productive/calm",
  "tags": ["标签1", "标签2"]
}

要求：
- 语气温暖、自然，像真人在写日记，不要像监控日志
- 不要编造数据中不存在的事件
- 不要包含 API Key、密码、token 等敏感信息
- 如果数据很少，写简短几行即可，不要硬凑字数
- 标签 1-3 个即可"""

SANITIZE_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "[API_KEY]"),
    (re.compile(r"Bearer\s+[a-zA-Z0-9\-_\.]+"), "[TOKEN]"),
    (re.compile(r"-----BEGIN[^-]*PRIVATE KEY-----[\s\S]*?-----END[^-]*PRIVATE KEY-----"), "[PRIVATE_KEY]"),
    (re.compile(r'Authorization:\s*[^\n]+'), "[AUTH_HEADER]"),
    (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), "[邮箱]"),
    (re.compile(r'[?&](token|key|secret|api_key|apikey|password)=[^&\s]+'), "?\\1=[REDACTED]"),
]


def _sanitize_text(text: str) -> str:
    for pattern, replacement in SANITIZE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _sanitize_context(ctx: dict) -> dict:
    """Strip sensitive fields from collected context. Applied to LLM prompt AND fallback."""
    if "messages" in ctx:
        for m in ctx["messages"]:
            if "content" in m:
                m["content"] = _sanitize_text(str(m["content"]))[:200]
    if "todos" in ctx:
        for t in ctx["todos"]:
            if "title" in t:
                t["title"] = _sanitize_text(str(t["title"]))
            if "notes" in t and t["notes"]:
                t["notes"] = _sanitize_text(str(t["notes"]))[:100]
    if "goals" in ctx:
        for g in ctx["goals"]:
            if "title" in g:
                g["title"] = _sanitize_text(str(g["title"]))
            if "description" in g and g["description"]:
                g["description"] = _sanitize_text(str(g["description"]))[:100]
    if "memories" in ctx:
        for mem in ctx["memories"]:
            if "content" in mem:
                mem["content"] = _sanitize_text(str(mem["content"]))[:200]
    # Remove sensitive top-level keys
    for key in ("api_key", "token", "password", "secret"):
        ctx.pop(key, None)
    return ctx


def _extract_json_object(text: str) -> dict:
    """Robust JSON extraction — handles fenced JSON and plain text fallback."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Fallback: raw text as content
    return {"title": cleaned[:50] or "今日日记", "content": cleaned[:500] or text[:500]}


class DiaryService:
    def __init__(
        self,
        db: Session,
        ai_client=None,
        config_service=None,
        emotion_service=None,
    ):
        self.db = db
        self.ai_client = ai_client
        self.config_service = config_service
        self.emotion_service = emotion_service

    # ── Existing methods ──

    def list_diaries(
        self, user_id: UUID, limit: int = 20, offset: int = 0, mood: str | None = None
    ) -> list[DiaryOut]:
        query = self.db.query(Diary).filter(Diary.user_id == user_id)
        if mood:
            query = query.filter(Diary.mood == mood)
        rows = query.order_by(Diary.date.desc()).offset(offset).limit(limit).all()
        return [DiaryOut.model_validate(row) for row in rows]

    def get_by_date(self, user_id: UUID, diary_date: date) -> DiaryDetail:
        row = (
            self.db.query(Diary)
            .filter(Diary.user_id == user_id, Diary.date == diary_date)
            .first()
        )
        if row is None:
            raise NotFoundError(f"No diary entry for {diary_date}")
        return DiaryDetail.model_validate(row)

    # ── Generate ──

    def generate(
        self,
        user_id: UUID,
        payload: DiaryGenerateRequest | None = None,
    ) -> DiaryGenerateResponse:
        # 1. Privacy gate
        if not self._is_diary_enabled(user_id):
            raise BadRequestError("Diary generation is disabled for this user")

        diary_date = self._parse_date(payload)
        force = payload.force if payload else False

        # 2. Return existing if not forced
        if not force:
            existing = (
                self.db.query(Diary)
                .filter(Diary.user_id == user_id, Diary.date == diary_date)
                .first()
            )
            if existing:
                return DiaryGenerateResponse.model_validate(existing)

        # 3. Collect context
        ctx = self._collect_context(user_id, diary_date)

        # 4. Sanitize
        ctx = _sanitize_context(ctx)

        # 5. Check sufficiency
        if not self._is_context_sufficient(ctx):
            result = self._build_fallback_diary(ctx)
        else:
            result = self._try_llm_generation(ctx, user_id)

        # 6. Save
        diary = self._save_diary(
            user_id=user_id,
            diary_date=diary_date,
            title=result.get("title", "今日日记"),
            content=result.get("content", ""),
            summary=result.get("summary", result.get("content", "")[:100]),
            mood=result.get("mood"),
            tags=result.get("tags") or [],
            source_ids=[str(cid) for cid in ctx.get("conversation_ids", [])],
            force=force,
        )
        return DiaryGenerateResponse.model_validate(diary)

    # ── Private helpers ──

    def _is_diary_enabled(self, user_id: UUID) -> bool:
        if self.config_service is None:
            return True
        try:
            val = self.config_service.get_effective_value(user_id, "diary_enabled")
            return val if isinstance(val, bool) else True
        except Exception as exc:
            logger.warning(
                "Failed to read diary_enabled for user_id=%s; denying diary generation (fail-closed)",
                user_id, exc_info=True,
            )
            return False

    def _parse_date(self, payload: DiaryGenerateRequest | None) -> date:
        if payload and payload.date:
            try:
                return date.fromisoformat(payload.date)
            except (ValueError, TypeError):
                raise BadRequestError(f"Invalid date format: {payload.date}")
        return date.today()

    def _collect_context(self, user_id: UUID, diary_date: date) -> dict:
        day_start = datetime(diary_date.year, diary_date.month, diary_date.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        # Conversations for this user
        conv_ids = [
            row[0]
            for row in self.db.query(Conversation.id)
            .filter(Conversation.user_id == user_id)
            .all()
        ]
        ctx: dict = {"conversation_ids": conv_ids, "date": diary_date.isoformat()}

        # Messages
        if conv_ids:
            messages = (
                self.db.query(Message)
                .filter(
                    Message.conversation_id.in_(conv_ids),
                    Message.created_at >= day_start,
                    Message.created_at < day_end,
                    Message.role.in_(["user", "assistant"]),
                )
                .order_by(Message.created_at.asc())
                .limit(60)
                .all()
            )
            ctx["messages"] = [
                {"role": m.role, "content": m.content[:200], "time": m.created_at.isoformat() if m.created_at else None}
                for m in messages
            ]
        else:
            ctx["messages"] = []

        # Todos — scoped to today: created, updated, or due today
        todos = (
            self.db.query(Todo)
            .filter(
                Todo.user_id == user_id,
                or_(
                    (Todo.created_at >= day_start) & (Todo.created_at < day_end),
                    (Todo.updated_at >= day_start) & (Todo.updated_at < day_end),
                    (Todo.due_at >= day_start) & (Todo.due_at < day_end),
                ),
            )
            .order_by(Todo.created_at.desc())
            .limit(20)
            .all()
        )
        ctx["todos"] = [
            {
                "title": t.title,
                "completed": t.completed,
                "notes": t.notes,
                "priority": t.priority,
            }
            for t in todos
        ]

        # Goals
        goals = (
            self.db.query(UserGoal)
            .filter(UserGoal.user_id == user_id)
            .order_by(UserGoal.updated_at.desc())
            .limit(10)
            .all()
        )
        ctx["goals"] = [
            {
                "title": g.title,
                "description": g.description,
                "status": g.status,
                "last_checked_at": g.last_checked_at.isoformat() if g.last_checked_at else None,
            }
            for g in goals
        ]

        # Emotions (computed on-the-fly, not a DB table)
        if self.emotion_service is not None and ctx.get("messages"):
            emotions = []
            for m in ctx["messages"]:
                if m.get("role") == "user" and m.get("content"):
                    try:
                        result = self.emotion_service.analyze(user_message=str(m["content"]))
                        if result and getattr(result, "emotion_label", None):
                            emotions.append(result.emotion_label)
                    except Exception:
                        pass
            if emotions:
                from collections import Counter
                ctx["dominant_emotions"] = [e for e, _ in Counter(emotions).most_common(3)]
            else:
                ctx["dominant_emotions"] = []
        else:
            ctx["dominant_emotions"] = []

        # Memories — only if enabled
        if self._memory_enabled(user_id):
            try:
                from app.models.memory import Memory
                memories = (
                    self.db.query(Memory)
                    .filter(
                        Memory.user_id == user_id,
                        Memory.archived.is_(False),
                        Memory.created_at >= day_start,
                        Memory.created_at < day_end,
                    )
                    .order_by(Memory.importance.desc())
                    .limit(20)
                    .all()
                )
                ctx["memories"] = [
                    {"content": m.content[:200], "category": m.category, "importance": m.importance}
                    for m in memories
                ]
            except Exception:
                ctx["memories"] = []
        else:
            ctx["memories"] = []

        return ctx

    def _memory_enabled(self, user_id: UUID) -> bool:
        try:
            from app.models.memory import MemoryPreference

            pref = (
                self.db.query(MemoryPreference)
                .filter(MemoryPreference.user_id == user_id)
                .first()
            )
            if pref is not None:
                return bool(pref.enabled)
        except Exception:
            pass
        return True  # default allow if no explicit preference

    def _is_context_sufficient(self, ctx: dict) -> bool:
        messages = ctx.get("messages") or []
        todos = ctx.get("todos") or []
        goals = ctx.get("goals") or []
        memories = ctx.get("memories") or []
        return len(messages) >= 3 or len(todos) > 0 or len(goals) > 0 or len(memories) > 0

    def _build_prompt(self, ctx: dict) -> str:
        parts = [DIARY_PROMPT, "", "## 今日数据"]
        parts.append(f"- 日期: {ctx.get('date', '')}")
        parts.append(f"- 消息数: {len(ctx.get('messages', []))}")
        parts.append(f"- 待办数: {len(ctx.get('todos', []))}")
        parts.append(f"- 目标数: {len(ctx.get('goals', []))}")
        if ctx.get("memories"):
            parts.append(f"- 记忆数: {len(ctx.get('memories', []))}")
        if ctx.get("dominant_emotions"):
            parts.append(f"- 主要情绪: {', '.join(ctx['dominant_emotions'])}")

        if ctx.get("messages"):
            parts.append("\n## 今日对话")
            for m in ctx["messages"]:
                role = "用户" if m.get("role") == "user" else "Shinobu"
                parts.append(f"{role}: {m.get('content', '')}")

        if ctx.get("todos"):
            parts.append("\n## 待办事项")
            for t in ctx["todos"]:
                status = "✓" if t.get("completed") else "○"
                parts.append(f"- [{status}] {t.get('title', '')}")

        if ctx.get("goals"):
            parts.append("\n## 目标")
            for g in ctx["goals"]:
                parts.append(f"- [{g.get('status', '')}] {g.get('title', '')}")

        prompt = "\n".join(parts)
        # Cap total prompt size
        if len(prompt) > 4000:
            prompt = prompt[:4000]
        return prompt

    def _try_llm_generation(self, ctx: dict, user_id: UUID) -> dict:
        prompt = self._build_prompt(ctx)
        result = self._call_llm(prompt, user_id)
        if result is not None:
            return result
        return self._build_fallback_diary(ctx)

    def _call_llm(self, prompt: str, user_id: UUID) -> dict | None:
        if self.ai_client is None:
            return None
        try:
            runtime_config = None
            if self.config_service is not None:
                try:
                    runtime_config = self.config_service.resolve_runtime(user_id)
                except Exception:
                    pass

            messages = [{"role": "user", "content": prompt}]
            response = self.ai_client.complete_chat(
                messages,
                max_tokens=1024,
                runtime_config=runtime_config,
            )
            content = response.get("content", "") if isinstance(response, dict) else str(response)
            if not content:
                return None

            parsed = _extract_json_object(content)

            # Mood whitelist
            VALID_MOODS = {"happy", "worried", "tired", "neutral", "productive", "calm"}
            raw_mood = str(parsed.get("mood") or "neutral").strip().lower()
            mood = raw_mood if raw_mood in VALID_MOODS else "neutral"

            # Tag normalization: flatten, strip, deduplicate, limit to 3
            raw_tags = parsed.get("tags", [])
            if isinstance(raw_tags, list):
                tags = [str(t).strip()[:20] for t in raw_tags if str(t).strip()][:3]
            else:
                tags = []

            return {
                "title": str(parsed.get("title") or "今日日记")[:50],
                "summary": str(parsed.get("summary") or parsed.get("content", ""))[:100],
                "content": str(parsed.get("content") or content)[:2000],
                "mood": mood,
                "tags": tags,
            }
        except Exception:
            logger.warning("LLM diary generation failed, using fallback", exc_info=True)
            return None

    def _build_fallback_diary(self, ctx: dict) -> dict:
        messages = ctx.get("messages") or []
        todos = ctx.get("todos") or []
        goals = ctx.get("goals") or []

        if not messages and not todos and not goals:
            return {
                "title": "平淡的一天",
                "summary": "今天似乎没有什么特别的事情发生。",
                "content": "今天没有太多互动。也许明天会有更多值得记录的时刻。",
                "mood": "neutral",
                "tags": ["日常"],
            }

        parts = []
        if messages:
            count = len(messages)
            parts.append(f"今天和用户进行了 {count} 条对话。")

        completed_todos = [t for t in todos if t.get("completed")]
        pending_todos = [t for t in todos if not t.get("completed")]
        if completed_todos:
            parts.append(f"完成了 {len(completed_todos)} 项待办：{'、'.join(t['title'][:20] for t in completed_todos[:3])}。")
        if pending_todos:
            parts.append(f"还有 {len(pending_todos)} 项待办未完成。")

        active_goals = [g for g in goals if g.get("status") == "active"]
        if active_goals:
            parts.append(f"持续跟进 {len(active_goals)} 个目标。")

        content = " ".join(parts) if parts else "今天没有太多互动。"
        summary = content[:100]

        return {
            "title": f"{ctx.get('date', '')} 日记",
            "summary": summary,
            "content": content,
            "mood": "neutral",
            "tags": ["日常"],
        }

    def _save_diary(
        self,
        user_id: UUID,
        diary_date: date,
        title: str,
        content: str,
        summary: str,
        mood: str | None,
        tags: list[str],
        source_ids: list[str],
        force: bool = False,
    ) -> Diary:
        existing = (
            self.db.query(Diary)
            .filter(Diary.user_id == user_id, Diary.date == diary_date)
            .first()
        )
        if existing and not force:
            return existing
        if existing and force:
            self.db.delete(existing)
            self.db.flush()

        diary = Diary(
            user_id=user_id,
            date=diary_date,
            title=title[:255],
            summary=summary[:2000],
            content=content[:5000],
            mood=mood[:50] if mood else None,
            tags=tags[:10],
            privacy="private",
            source_conversation_ids=source_ids[:20],
        )
        self.db.add(diary)
        self.db.commit()
        self.db.refresh(diary)
        return diary
