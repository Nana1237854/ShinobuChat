"""Tool: open_local_app (F12).

Registered in ToolRegistry. The handler delegates to LocalAppService.open_app()
— it does NOT contain its own subprocess logic.
"""

import json

from app.services.tool_registry import Tool, ToolContext


def create_tool(registry) -> Tool:
    def handler(arguments: dict, context: ToolContext) -> str:
        user_id = context.user_id
        conversation_id = context.conversation_id
        app_key = arguments.get("app_key") or None
        intent_type = arguments.get("intent_type") or None

        if not app_key and not intent_type:
            return json.dumps(
                {"error": "Either app_key or intent_type must be provided."},
                ensure_ascii=False,
            )

        # Import here to avoid circular imports at module level
        from app.db.session import SessionLocal
        from app.services.local_app_service import LocalAppService

        db = SessionLocal()
        try:
            svc = LocalAppService(db)
            result = svc.open_app(
                user_id,
                app_key=app_key,
                intent_type=intent_type,
                conversation_id=conversation_id,
                source="agent_tool",
            )
            return json.dumps(result, ensure_ascii=False, default=str)
        finally:
            db.close()

    return Tool(
        name="open_local_app",
        description=(
            "Open a local application configured by the user. "
            "Provide either 'app_key' (e.g. 'music') or 'intent_type' "
            "(e.g. 'open_music'). An optional 'reason' can explain why "
            "the tool was invoked."
        ),
        parameters={
            "type": "object",
            "properties": {
                "app_key": {
                    "type": "string",
                    "description": "User-configured app key, e.g. 'music' or 'vscode'.",
                },
                "intent_type": {
                    "type": "string",
                    "description": "System intent type, e.g. 'open_music' or 'open_browser'.",
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
