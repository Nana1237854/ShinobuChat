from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from app.db.session import SessionLocal
from app.schemas.context_intent import ContextIntentResult
from app.services.turn.turn_state import MessageTurnState


@dataclass
class ContextDirectAction:
    """Lightweight direct-action-like object, fully compatible with
    DirectActionPlan fields used by build_reply() and StreamEventService.action().
    """
    action: str = "open_local_app"
    intent_type: str | None = None
    app_key: str | None = None
    app_name: str | None = None
    query: str | None = None
    label: str = ""
    confidence: float = 0.0


_RELAUNCH_PATTERNS: list[re.Pattern] = [
    re.compile(p)
    for p in [
        r"重新打开",
        r"重启",
        r"再开一[个下]",
        r"再打开",
        r"关掉再打开",
        r"关掉再开",
        r"重新启动",
        r"再启动",
        r"再运行",
    ]
]


def _is_relaunch_intent(user_text: str) -> bool:
    """Return True when the user explicitly asks to re-launch / restart."""
    text = (user_text or "").strip()
    if not text:
        return False
    return any(p.search(text) for p in _RELAUNCH_PATTERNS)


@dataclass
class DirectActionResult:
    action_result: dict
    pending_info: dict | None
    assistant_reply: str


class DirectActionRunner:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def run(self, user_id: UUID, state: MessageTurnState) -> DirectActionResult:
        da = state.direct_action
        if da is None:
            raise ValueError("direct_action is required")

        from app.domains.local_agent.local_agent_settings_service import LocalAgentSettingsService
        from app.domains.local_agent.local_app_service import LocalAppService

        db = self.session_factory()
        try:
            # F16: check permission before executing quick-intent direct action
            settings_svc = LocalAgentSettingsService(db)
            if not settings_svc.is_local_launcher_enabled(user_id):
                result = {
                    "status": "forbidden",
                    "message": "Local Launcher 已关闭。请在设置 → 权限中心中开启后再试。",
                }
                return DirectActionResult(
                    action_result=result,
                    pending_info=None,
                    assistant_reply=self.build_reply(da, result),
                )

            user_text = (
                getattr(da, "query", None)
                or (state.user_message.content if state.user_message else None)
                or ""
            )
            force_relaunch = _is_relaunch_intent(user_text)

            svc = LocalAppService(db)
            result = svc.open_app(
                user_id,
                intent_type=da.intent_type,
                app_key=da.app_key or None,
                app_name=getattr(da, "app_name", None) or None,
                query=user_text,
                conversation_id=state.conversation.id,
                source="quick_intent",
                force_relaunch=force_relaunch,
            )

            pending_action_id = result.get("pending_action_id")

            pending_info = None
            if result.get("status") == "requires_confirmation" and pending_action_id:
                pending_info = {
                    "id": pending_action_id,
                    "pending_action_id": pending_action_id,
                    "user_id": str(user_id),
                    "conversation_id": str(state.conversation.id),
                    "action_type": da.action,
                    "app_key": result.get("app_key"),
                    "display_name": result.get("display_name"),
                    "description": result.get("message") or f"{result.get('display_name') or result.get('app_key') or '应用'} 请求你的确认",
                    "intent_type": da.intent_type,
                    "status": "waiting_confirmation",
                    "expires_at": result.get("expires_at"),
                    "created_at": result.get("created_at"),
                }

            return DirectActionResult(
                action_result=result,
                pending_info=pending_info,
                assistant_reply=self.build_reply(da, result),
            )
        finally:
            db.close()

    def run_from_context_intent(
        self, user_id: UUID, state: MessageTurnState, intent: ContextIntentResult
    ) -> DirectActionResult:
        """Execute an action resolved by ContextIntentResolver.

        Applies F16 permission check before calling LocalAppService.open_app().
        Does NOT pass force_relaunch / bring_to_front — those are v1 hints only.
        """
        from app.domains.local_agent.local_agent_settings_service import LocalAgentSettingsService
        from app.domains.local_agent.local_app_service import LocalAppService

        db = self.session_factory()
        try:
            # F16: permission check FIRST
            settings_svc = LocalAgentSettingsService(db)
            if not settings_svc.is_local_launcher_enabled(user_id):
                return DirectActionResult(
                    action_result={"status": "forbidden", "message": "Local Launcher 已关闭"},
                    pending_info=None,
                    assistant_reply=self.build_reply(
                        ContextDirectAction(
                            intent_type=intent.intent_type,
                            app_name=intent.app_name,
                        ),
                        {"status": "forbidden"},
                    ),
                )

            svc = LocalAppService(db)
            result = svc.open_app(
                user_id,
                intent_type=intent.intent_type,
                app_key=intent.app_key or None,
                app_name=intent.app_name or None,
                query=intent.query or state.user_message.content,
                conversation_id=state.conversation.id,
                source="context_intent",
            )

            pending_info = None
            pid = result.get("pending_action_id")
            if result.get("status") == "requires_confirmation" and pid:
                pending_info = {
                    "id": pid,
                    "pending_action_id": pid,
                    "user_id": str(user_id),
                    "conversation_id": str(state.conversation.id),
                    "action_type": "open_local_app",
                    "app_key": result.get("app_key"),
                    "display_name": result.get("display_name"),
                    "description": result.get("message") or "",
                    "intent_type": intent.intent_type,
                    "status": "waiting_confirmation",
                    "expires_at": result.get("expires_at"),
                    "created_at": result.get("created_at"),
                }

            da = ContextDirectAction(
                intent_type=intent.intent_type,
                app_key=intent.app_key,
                app_name=intent.app_name,
                query=intent.query,
            )
            return DirectActionResult(
                action_result=result,
                pending_info=pending_info,
                assistant_reply=self.build_reply(da, result),
            )
        finally:
            db.close()

    @staticmethod
    def build_reply(da, result: dict) -> str:
        status = result.get("status", "failed")
        display_name = result.get("display_name", "")
        selection_message = result.get("selection_message") or ""
        candidates = result.get("candidates")
        intent_type = da.intent_type or ""

        if status == "opened":
            return f"[happy]好的，已为你打开 {display_name}~"

        if status == "requires_confirmation":
            if selection_message:
                return f"[thinking]{selection_message} {display_name} 需要确认才能打开，请确认一下~"
            return f"[thinking]{display_name} 需要确认才能打开哦，请确认一下~"

        if status == "not_configured":
            message = result.get("message", "")
            if message:
                return f"[neutral]{message}"
            return f"[neutral]我还没配置 {intent_type} 对应的应用呢，去设置里绑定一下吧~"

        if status == "requires_selection":
            if candidates:
                names = ", ".join(
                    c.get("display_name", c.get("app_key", "")) for c in candidates
                )
                return f"[thinking]有多个应用匹配 {intent_type}，请在设置中选择一个默认应用，或者直接告诉我要打开 {names}。"
            message = result.get("message", "")
            if message:
                return f"[thinking]{message}"
            return f"[thinking]有多个应用匹配 {intent_type}，请在设置中选择一个默认应用~"

        if status == "forbidden":
            return f"[neutral]{result.get('message', 'Local Launcher 已关闭。')}"

        return f"[neutral]抱歉，打开 {display_name or intent_type} 失败了，可能是路径有问题，去检查一下吧~"
