from app.services.tool_registry import Tool, ToolContext


def create_tool(registry) -> Tool:
    def handler(arguments: dict, context: ToolContext) -> str:
        limit = int(arguments.get("limit") or 20)
        items = context.history[-limit:]
        lines = [
            f"{message.created_at.isoformat()} {message.role}: {message.content}"
            for message in items
        ]
        return "\n".join(lines)

    return Tool(
        name="conversation_digest",
        description="Return recent conversation messages for review, TODO extraction, or inspiration organization.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
        },
        handler=handler,
    )
