"""ToolRegistry tool: search_web — Google Custom Search with per-user config."""

import json

from app.services.config_service import ConfigService
from app.services.tool_registry import Tool, ToolContext
from app.domains.browser.web_search_service import WebSearchService


def create_tool(registry) -> Tool:
    def handler(arguments: dict, context: ToolContext) -> str:
        query = str(arguments.get("query", ""))
        max_results = int(arguments.get("max_results") or 5)

        api_key = ""
        cx = ""

        if registry.session_factory and context.user_id:
            db = registry.session_factory()
            try:
                config = ConfigService(db)
                api_key = config.get_effective_value(context.user_id, "google_search_api_key") or ""
                cx = config.get_effective_value(context.user_id, "google_search_cx") or ""
            finally:
                db.close()

        svc = WebSearchService(api_key=api_key, cx=cx)
        result = svc.search(query, user_id=context.user_id, max_results=max_results)
        return json.dumps(result, ensure_ascii=False)

    return Tool(
        name="search_web",
        description="Search the web using the configured Google Custom Search API.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query"],
        },
        handler=handler,
    )
