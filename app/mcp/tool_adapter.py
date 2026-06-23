"""MCP tool adapter — maps MCP-safe tools to internal handlers (F14.5)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from uuid import UUID

logger = logging.getLogger(__name__)


class McpToolAdapter:
    """Registers MCP-exposable tools and their handlers.

    Each tool has a name, description, JSON Schema input, and handler.
    Only tools in MCP_SAFE_TOOLS are registered.
    """

    def __init__(self, internal_registry=None) -> None:
        self._tools: dict[str, dict] = {}
        self._registry = internal_registry

    def register(self, name: str, description: str, input_schema: dict, handler: Callable) -> None:
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "handler": handler,
        }

    def list_tools(self) -> list[dict]:
        return [
            {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
            for t in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            result = tool["handler"](arguments)
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.exception("MCP tool %s failed", name)
            return json.dumps({"error": str(exc)})


def create_default_adapter() -> McpToolAdapter:
    """Create an adapter pre-loaded with MCP-safe tools."""
    from app.core.url_validation import validate_url_safe
    from app.services.browser_automation_service import BrowserAutomationService
    from app.services.web_reader_service import WebReaderService
    from app.services.web_search_service import WebSearchService

    adapter = McpToolAdapter()

    # -- open_url --
    browser_svc = BrowserAutomationService()

    def open_url_handler(args: dict) -> dict:
        url = args.get("url", "")
        validate_url_safe(url)
        return browser_svc.open_url(url)

    adapter.register(
        name="open_url",
        description="Open a URL in the default browser.",
        input_schema={
            "type": "object",
            "properties": {"url": {"type": "string", "description": "A public http/https URL."}},
            "required": ["url"],
        },
        handler=open_url_handler,
    )

    # -- read_webpage --
    reader_svc = WebReaderService()

    def read_webpage_handler(args: dict) -> dict:
        url = args.get("url", "")
        max_chars = int(args.get("max_chars", 10000))
        return reader_svc.read(url, max_chars=min(max_chars, 50000))

    adapter.register(
        name="read_webpage",
        description="Read a web page and return its text content.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "A public http/https URL."},
                "max_chars": {"type": "integer", "description": "Max characters to return."},
            },
            "required": ["url"],
        },
        handler=read_webpage_handler,
    )

    # -- search_web --
    search_svc = WebSearchService()

    def search_web_handler(args: dict) -> dict:
        query = args.get("query", "")
        return search_svc.search(query, max_results=5)

    adapter.register(
        name="search_web",
        description="Search the web using Google Custom Search.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query."}},
            "required": ["query"],
        },
        handler=search_web_handler,
    )

    # -- open_local_app (stub) --
    def open_local_app_handler(args: dict) -> dict:
        return {
            "status": "not_implemented",
            "message": "open_local_app via MCP requires a connected backend. Use the ShinobuChat UI.",
        }

    adapter.register(
        name="open_local_app",
        description="Launch a locally configured application.",
        input_schema={
            "type": "object",
            "properties": {
                "app_key": {"type": "string", "description": "Registered app key."},
            },
            "required": ["app_key"],
        },
        handler=open_local_app_handler,
    )

    return adapter
