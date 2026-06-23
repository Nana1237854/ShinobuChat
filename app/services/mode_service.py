import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user_mode_settings import UserModeSettings
from app.schemas.mode import (
    MODE_DESCRIPTIONS,
    MODE_LABELS,
    ConversationMode,
    ConversationModeResponse,
    ConversationModeUpdate,
    ModeBehaviorOut,
    ModeDecisionTendency,
    ModeReminderPolicy,
    ModeReplyPolicy,
    ModeToolPolicy,
)

logger = logging.getLogger(__name__)

# ── Behaviour policy tables ──

TOOL_POLICIES: dict[str, ModeToolPolicy] = {
    "companion": ModeToolPolicy(
        allowed_tool_groups=["chat", "memory", "reminder", "emotion"],
        blocked_tool_groups=["shell", "web_search"],
    ),
    "work": ModeToolPolicy(
        allowed_tool_groups=["chat", "memory", "reminder", "todo", "goal", "web_search"],
        blocked_tool_groups=["shell", "code_exec"],
    ),
    "focus": ModeToolPolicy(
        allowed_tool_groups=["todo", "goal", "reminder"],
        blocked_tool_groups=["chat", "shell", "web_search", "code_exec", "emotion"],
    ),
    "night": ModeToolPolicy(
        allowed_tool_groups=["chat", "reminder"],
        blocked_tool_groups=["shell", "web_search", "code_exec", "todo", "goal"],
    ),
}

REPLY_POLICIES: dict[str, ModeReplyPolicy] = {
    "companion": ModeReplyPolicy(
        max_sentences=3, style="natural", prioritize_conciseness=False,
    ),
    "work": ModeReplyPolicy(
        max_sentences=5, style="structured", prioritize_conciseness=True,
    ),
    "focus": ModeReplyPolicy(
        max_sentences=1, style="minimal", prioritize_conciseness=True,
    ),
    "night": ModeReplyPolicy(
        max_sentences=2, style="soft", prioritize_conciseness=True,
    ),
}

REMINDER_POLICIES: dict[str, ModeReminderPolicy] = {
    "companion": ModeReminderPolicy(
        enabled=True, reduce_frequency=False, urgent_only=False, tone="friendly",
    ),
    "work": ModeReminderPolicy(
        enabled=True, reduce_frequency=False, urgent_only=False, tone="task_oriented",
    ),
    "focus": ModeReminderPolicy(
        enabled=True, reduce_frequency=True, urgent_only=True, tone="brief",
    ),
    "night": ModeReminderPolicy(
        enabled=True, reduce_frequency=True, urgent_only=True, tone="quiet",
    ),
}

DECISION_TENDENCIES: dict[str, ModeDecisionTendency] = {
    "companion": ModeDecisionTendency(
        chat_weight=0.8, agent_weight=0.2, prefer_todo_create=False,
        prefer_task_planning=False, suppress_idle_chat=False,
    ),
    "work": ModeDecisionTendency(
        chat_weight=0.4, agent_weight=0.6, prefer_todo_create=True,
        prefer_task_planning=True, suppress_idle_chat=False,
    ),
    "focus": ModeDecisionTendency(
        chat_weight=0.1, agent_weight=0.9, prefer_todo_create=True,
        prefer_task_planning=False, suppress_idle_chat=True,
    ),
    "night": ModeDecisionTendency(
        chat_weight=0.9, agent_weight=0.1, prefer_todo_create=False,
        prefer_task_planning=False, suppress_idle_chat=True,
    ),
}

# ── Prompt sections (Chinese, injected into roleplay system prompt) ──

ROLEPLAY_PROMPT_SECTIONS: dict[str, str] = {
    "companion": "",
    "work": (
        "当前处于工作模式。回复需结构化，优先给出结论、步骤或清单。"
        "保持简洁专业，但不要失去 Shinobu 的温暖语调。"
    ),
    "focus": (
        "当前处于专注模式。只回复用户明确提出的问题，不主动闲聊。"
        "如果不需要回复，可以直接用简短确认收尾。"
    ),
    "night": (
        "当前处于夜间模式。语气轻柔，回复更短更温暖，减少打扰感。"
        "用更安静的方式陪伴用户。"
    ),
}


class ModeService:
    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ──

    def get_settings(self, user_id: UUID) -> ConversationModeResponse:
        row = self._get_or_create_row(user_id)
        return self._build_response(row)

    def get_mode(self, user_id: UUID) -> ConversationMode:
        row = self._get_or_create_row(user_id)
        return ConversationMode(row.mode)

    def update_settings(
        self, user_id: UUID, payload: ConversationModeUpdate
    ) -> ConversationModeResponse:
        row = self._get_or_create_row(user_id)
        row.mode = payload.mode.value
        self.db.commit()
        self.db.refresh(row)
        return self._build_response(row)

    def _get_or_create_row(self, user_id: UUID) -> UserModeSettings:
        row = (
            self.db.query(UserModeSettings)
            .filter(UserModeSettings.user_id == user_id)
            .first()
        )
        if row is None:
            row = UserModeSettings(user_id=user_id, mode="companion")
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def _build_response(self, row: UserModeSettings) -> ConversationModeResponse:
        mode = ConversationMode(row.mode)
        behavior = self.get_mode_behavior(row.user_id)
        return ConversationModeResponse(
            mode=mode,
            mode_label=MODE_LABELS.get(row.mode, row.mode),
            description=MODE_DESCRIPTIONS.get(row.mode, ""),
            behavior=behavior,
            updated_at=row.updated_at,
        )

    # ── Behavior ──

    def get_mode_behavior(self, user_id: UUID) -> ModeBehaviorOut:
        row = self._get_or_create_row(user_id)
        mode = row.mode
        return ModeBehaviorOut(
            mode=ConversationMode(mode),
            mode_label=MODE_LABELS.get(mode, mode),
            description=MODE_DESCRIPTIONS.get(mode, ""),
            tool_policy=TOOL_POLICIES.get(mode, TOOL_POLICIES["companion"]),
            reply_policy=REPLY_POLICIES.get(mode, REPLY_POLICIES["companion"]),
            reminder_policy=REMINDER_POLICIES.get(mode, REMINDER_POLICIES["companion"]),
            decision_tendency=DECISION_TENDENCIES.get(mode, DECISION_TENDENCIES["companion"]),
        )

    # ── Policies (stateless helpers) ──

    def build_roleplay_prompt_section(self, mode: str) -> str:
        return ROLEPLAY_PROMPT_SECTIONS.get(mode, "")

    def get_tool_policy(self, mode: str) -> ModeToolPolicy:
        return TOOL_POLICIES.get(mode, TOOL_POLICIES["companion"])

    def get_reminder_policy(self, mode: str) -> ModeReminderPolicy:
        return REMINDER_POLICIES.get(mode, REMINDER_POLICIES["companion"])

    def get_reply_policy(self, mode: str) -> ModeReplyPolicy:
        return REPLY_POLICIES.get(mode, REPLY_POLICIES["companion"])

    def get_decision_tendency(self, mode: str) -> ModeDecisionTendency:
        return DECISION_TENDENCIES.get(mode, DECISION_TENDENCIES["companion"])
