from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.db.session import SessionLocal
from app.services.turn.turn_state import MessageTurnState


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

        from app.services.local_agent_settings_service import LocalAgentSettingsService
        from app.services.local_app_service import LocalAppService

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

            svc = LocalAppService(db)
            result = svc.open_app(
                user_id,
                intent_type=da.intent_type,
                app_key=da.app_key,
                conversation_id=state.conversation.id,
                source="quick_intent",
            )

            pending_info = None
            if result.get("status") == "requires_confirmation":
                pending_info = {
                    "pending_action_id": result.get("pending_action_id"),
                    "action_type": da.action,
                    "app_key": result.get("app_key"),
                    "display_name": result.get("display_name"),
                    "intent_type": da.intent_type,
                    "status": "waiting_confirmation",
                }

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
        display_name = result.get("display_name", da.intent_type)

        if status == "opened":
            return f"[happy]好的，已为你打开 {display_name}~"
        if status == "requires_confirmation":
            return f"[thinking]{display_name} 需要确认才能打开哦，请确认一下~"
        if status == "not_configured":
            return f"[neutral]我还没配置 {da.intent_type} 对应的应用呢，去设置里绑定一下吧~"
        if status == "requires_selection":
            return f"[thinking]有多个应用匹配 {da.intent_type}，请在设置中选择一个默认应用~"
        return f"[neutral]抱歉，打开 {display_name} 失败了，可能是路径有问题，去检查一下吧~"
