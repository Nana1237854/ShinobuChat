import json

from app.services.tool_registry import Tool, ToolContext
from app.domains.browser.web_reader_service import WebReaderService


def create_tool(registry) -> Tool:
    reader = WebReaderService(registry.http_client)

    def handler(arguments: dict, context: ToolContext) -> str:
        url = str(arguments.get("url", ""))
        max_chars = int(arguments.get("max_chars") or 10000)

        result = reader.read(url, user_id=context.user_id, max_chars=max_chars)
        if result["status"] != "ok":
            return json.dumps({"error": result.get("message", "Fetch failed")}, ensure_ascii=False)

        return result["content"][:max_chars]

    return Tool(
        name="fetch_web_page",
        description="Fetch a webpage and return text content for summarization.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 500, "maximum": 20000},
            },
            "required": ["url"],
        },
        handler=handler,
    )
