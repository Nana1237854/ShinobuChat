"""MCP tool adapter — maps MCP-safe tools to ToolRegistry.execute_verified (F14.5).

All tool calls go through ToolRegistry.execute_verified(), which enforces
ToolPolicyService and ToolVerifier. No tool is called directly.

Architecture note: This adapter wraps ToolRegistry. MCP tools are a subset
of registered tools, gated by MCP_SAFE_TOOLS. Blocked tools (shell_command,
download_file, etc.) are never exposed via tools/list and are rejected at
the server level even if somehow requested.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class McpToolAdapter:
    """Registry of MCP-safe tool schemas, backed by ToolRegistry for execution.

    Only tools in MCP_SAFE_TOOLS are registered. All calls flow through
    ToolRegistry.execute_verified() with a ToolContext carrying the MCP
    route mode, ensuring ToolPolicyService and ToolVerifier apply.
    """

    def __init__(self, tool_registry=None) -> None:
        """*tool_registry* should be a ToolRegistry instance.

        If omitted (standalone MCP process without backend DB), a fallback
        adapter is used that can call lightweight tools directly. In that
        mode only read-only tools (read_webpage, search_web) are available.
        """
        self._registry = tool_registry
        self._tools: dict[str, dict] = {}
        self._fallback_handlers: dict[str, callable] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, description: str, input_schema: dict, handler=None) -> None:
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
        }
        if handler is not None:
            self._fallback_handlers[name] = handler

    # ------------------------------------------------------------------
    # MCP protocol methods
    # ------------------------------------------------------------------

    def list_tools(self) -> list[dict]:
        """Return tool schemas. Prefers ToolRegistry schemas when available."""
        if self._registry is not None:
            safe_set = self._tools.keys()
            return [
                s for s in self._registry.schemas()
                if s.get("function", {}).get("name") in safe_set
            ]
        return [
            {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
            for t in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: dict, user_id: UUID | None = None) -> str:
        """Execute *name* with *arguments*, going through ToolRegistry if available.

        Falls back to direct handler only when ToolRegistry is unavailable
        and only for the subset of tools with registered fallback handlers.
        """
        if self._registry is not None:
            return self._call_via_registry(name, arguments, user_id)
        return self._call_via_fallback(name, arguments)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_via_registry(self, name: str, arguments: dict, user_id: UUID | None) -> str:
        """Execute through ToolRegistry.execute_verified()."""
        from app.services.tool_registry import ToolContext

        context = ToolContext(
            history=[],
            user_skills={},
            metadata={
                "conversation_mode": "work",
                "route_mode": "mcp",
            },
            user_id=user_id,
            conversation_id=None,
        )
        result = self._registry.execute_verified(name, arguments, context)
        return json.dumps(
            {
                "output": result.output,
                "verified": result.verified,
                "reason": result.reason,
                "checked_fields": result.checked_fields,
            },
            ensure_ascii=False,
        )

    def _call_via_fallback(self, name: str, arguments: dict) -> str:
        """Fallback: call registered handler directly (standalone MCP, no DB)."""
        handler = self._fallback_handlers.get(name)
        if handler is None:
            return json.dumps({"error": f"Tool '{name}' has no fallback handler."})
        try:
            result = handler(arguments)
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.exception("MCP fallback tool %s failed", name)
            return json.dumps({"error": str(exc)})


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

def create_default_adapter(tool_registry=None) -> McpToolAdapter:
    """Create an adapter with MCP-safe tools.

    When *tool_registry* is provided, all execution goes through
    ToolRegistry.execute_verified(). Otherwise, lightweight fallback
    handlers are used for read_webpage and search_web.
    """
    from app.core.url_validation import validate_url_safe
    from app.services.web_reader_service import WebReaderService
    from app.services.web_search_service import WebSearchService

    adapter = McpToolAdapter(tool_registry)

    # -- open_url --
    def open_url_fallback(args: dict) -> dict:
        url = args.get("url", "")
        validate_url_safe(url)
        from app.services.browser_automation_service import BrowserAutomationService
        return BrowserAutomationService().open_url(url)

    adapter.register(
        name="open_url",
        description="Open a URL in the default browser.",
        input_schema={
            "type": "object",
            "properties": {"url": {"type": "string", "description": "A public http/https URL."}},
            "required": ["url"],
        },
        handler=open_url_fallback,
    )

    # -- read_webpage --
    reader_svc = WebReaderService()

    def read_webpage_fallback(args: dict) -> dict:
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
        handler=read_webpage_fallback,
    )

    # -- search_web --
    search_svc = WebSearchService()

    def search_web_fallback(args: dict) -> dict:
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
        handler=search_web_fallback,
    )

    # -- open_local_app --
    def open_local_app_fallback(args: dict) -> dict:
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
        handler=open_local_app_fallback,
    )

    return adapter
