"""ToolRegistry tool: read_webpage — read a public webpage via WebReaderService."""

import json

from app.services.tool_registry import Tool, ToolContext
from app.domains.browser.web_reader_service import WebReaderService


def create_tool(registry) -> Tool:
    reader = WebReaderService(registry.http_client)

    def handler(arguments: dict, context: ToolContext) -> str:
        url = str(arguments.get("url", ""))
        max_chars = int(arguments.get("max_chars") or 10000)
        result = reader.read(url, user_id=context.user_id, max_chars=max_chars)
        return json.dumps(result, ensure_ascii=False)

    return Tool(
        name="read_webpage",
        description="Read a public webpage and return title, text content, links, and metadata.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 500, "maximum": 50000},
            },
            "required": ["url"],
        },
        handler=handler,
    )
