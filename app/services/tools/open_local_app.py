"""Tool: open_local_app (F12).

Registered in ToolRegistry. The handler delegates to LocalAppService.open_app()
— it does NOT contain its own subprocess logic.

When the result is ``requires_confirmation``, the handler writes a
``pending_action`` dict into ``context.metadata`` so that the downstream
AgentOrchestrator / MessageService can emit it as an SSE event and include
it in the ``done`` payload.
"""

import json

from app.services.tool_registry import Tool, ToolContext


def create_tool(registry) -> Tool:
    def handler(arguments: dict, context: ToolContext) -> str:
        user_id = context.user_id
        conversation_id = context.conversation_id
        app_key = arguments.get("app_key") or None
        intent_type = arguments.get("intent_type") or None
        app_name = arguments.get("app_name") or None
        query = arguments.get("query") or arguments.get("reason") or None

        if not app_key and not intent_type and not app_name and not query:
            return json.dumps(
                {"error": "Either app_key, intent_type, app_name, or query must be provided."},
                ensure_ascii=False,
            )

        # Permission check (F16)
        from app.db.session import SessionLocal
        from app.domains.local_agent.local_agent_settings_service import LocalAgentSettingsService
        from app.domains.local_agent.local_app_service import LocalAppService

        db = SessionLocal()
        try:
            settings_svc = LocalAgentSettingsService(db)
            if not settings_svc.is_local_launcher_enabled(user_id):
                context.metadata["action_log"] = {
                    "action": "open_local_app",
                    "intent_type": intent_type or "",
                    "status": "forbidden",
                    "message": "Local Launcher 已关闭。请在设置 → 权限中心中开启后再试。",
                    "app_key": app_key,
                    "display_name": app_name,
                    "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                }
                return json.dumps(
                    {"error": "Local Launcher 已关闭。请在设置 → 权限中心中开启后再试。"},
                    ensure_ascii=False,
                )

            svc = LocalAppService(db)
            result = svc.open_app(
                user_id,
                app_key=app_key,
                intent_type=intent_type,
                app_name=app_name,
                query=query,
                conversation_id=conversation_id,
                source="agent_tool",
            )

            # Write action_log into context.metadata so the
            # AgentOrchestrator can forward it to the frontend as an
            # SSE ``action`` event (local operation log panel).
            from datetime import datetime as _dt

            action_status = result.get("status", "unknown")
            context.metadata["action_log"] = {
                "action": "open_local_app",
                "intent_type": intent_type or "",
                "status": action_status,
                "message": result.get("message", ""),
                "app_key": result.get("app_key"),
                "display_name": result.get("display_name"),
                "timestamp": _dt.utcnow().isoformat() + "Z",
            }

            # Write pending_action into context.metadata so the
            # AgentOrchestrator / MessageService can forward it to the
            # frontend as an SSE ``pending_action`` event and include it
            # in the ``done`` payload.
            if result.get("status") == "requires_confirmation" and result.get("pending_action_id"):
                context.metadata["pending_action"] = {
                    "id": result["pending_action_id"],
                    "pending_action_id": result["pending_action_id"],
                    "user_id": str(user_id),
                    "conversation_id": str(conversation_id) if conversation_id else "",
                    "action_type": "open_local_app",
                    "app_key": result.get("app_key", ""),
                    "display_name": result.get("display_name", ""),
                    "description": result.get("message")
                        or f"{result.get('display_name') or result.get('app_key') or '应用'} 请求你的确认",
                    "intent_type": intent_type or "",
                    "status": "waiting_confirmation",
                    "expires_at": result.get("expires_at"),
                    "created_at": result.get("created_at"),
                }

            return json.dumps(result, ensure_ascii=False, default=str)
        finally:
            db.close()

    return Tool(
        name="open_local_app",
        description=(
            "Open a local application configured by the user. "
            "Provide 'app_key' (e.g. 'CloudMusic'), 'intent_type' "
            "(e.g. 'open_music', 'open_ide'), 'app_name' (the display name "
            "the user mentioned like '网易云音乐' or 'vscode'), or 'query' "
            "(the user's full request for fuzzy matching). "
            "An optional 'reason' can explain why the tool was invoked."
        ),
        parameters={
            "type": "object",
            "properties": {
                "app_key": {
                    "type": "string",
                    "description": "User-configured app key, e.g. 'CloudMusic', 'vscode'.",
                },
                "intent_type": {
                    "type": "string",
                    "description": "System intent type, e.g. 'open_music', 'open_ide', 'open_browser'.",
                },
                "app_name": {
                    "type": "string",
                    "description": "Natural language app name explicitly mentioned by the user, e.g. '网易云音乐', 'vscode', 'Android Studio'.",
                },
                "query": {
                    "type": "string",
                    "description": "Original user request or app phrase used for fuzzy matching.",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why this tool was called.",
                },
            },
            "required": [],
        },
        handler=handler,
    )
