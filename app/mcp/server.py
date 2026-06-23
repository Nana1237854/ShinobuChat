"""MCP Server entry point (F14.5).

Run as a standalone process:
    python -m app.mcp.server

Implements a minimal MCP-compatible stdio JSON-RPC server.
Only exposes tools listed in MCP_SAFE_TOOLS.

When SC_MCP_ENABLED=true, initialises the real ToolRegistry so that
every tools/call flows through ToolRegistry.execute_verified(), which
enforces ToolPolicyService + ToolVerifier.

Requires SC_MCP_DEFAULT_USER_ID for tools that need user context
(e.g. open_local_app, search_web).
"""

from __future__ import annotations

import json
import logging
import sys
from uuid import UUID

from app.mcp.config import MCP_BLOCKED_TOOLS, MCP_DEFAULT_USER_ID, MCP_ENABLED, MCP_SAFE_TOOLS
from app.mcp.tool_adapter import create_default_adapter

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-server")

_USER_CONTEXT_REQUIRED_TOOLS: set[str] = {"open_local_app"}


def _send(response: dict) -> None:
    line = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _resolve_default_user_id() -> UUID | None:
    if not MCP_DEFAULT_USER_ID:
        return None
    try:
        return UUID(MCP_DEFAULT_USER_ID)
    except ValueError:
        logger.error("Invalid SC_MCP_DEFAULT_USER_ID: %s", MCP_DEFAULT_USER_ID)
        return None


def handle_request(request: dict, adapter, default_user_id: UUID | None = None) -> dict | None:
    method = request.get("method", "")
    req_id = request.get("id")

    # Defense-in-depth: reject tool-related calls when MCP is disabled
    if not MCP_ENABLED and method in ("tools/list", "tools/call"):
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32001, "message": "MCP is disabled. Set SC_MCP_ENABLED=true."},
        }

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "ShinobuChat MCP Adapter",
                    "version": "0.1.0",
                },
            },
        }

    if method == "notifications/initialized":
        return None  # No response for notifications

    if method == "tools/list":
        tools = adapter.list_tools()
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

    if method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name", "")

        if tool_name in MCP_BLOCKED_TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(
                        {"error": f"Tool '{tool_name}' is blocked for MCP use."}
                    )}],
                    "isError": True,
                },
            }

        if tool_name not in MCP_SAFE_TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(
                        {"error": f"Tool '{tool_name}' is not available via MCP."}
                    )}],
                    "isError": True,
                },
            }

        # User-context gate: tools that need a real user must have one configured
        if tool_name in _USER_CONTEXT_REQUIRED_TOOLS and default_user_id is None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(
                        {"error": "SC_MCP_DEFAULT_USER_ID is required for this tool."}
                    )}],
                    "isError": True,
                },
            }

        arguments = params.get("arguments", {})
        result_text = adapter.call_tool(tool_name, arguments, user_id=default_user_id)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": result_text}],
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def run_stdio() -> None:
    """Run the MCP server in stdio mode."""
    if not MCP_ENABLED:
        logger.warning("MCP is disabled. Set SC_MCP_ENABLED=true to enable. Exiting.")
        _send({
            "jsonrpc": "2.0",
            "method": "log",
            "params": {
                "level": "warning",
                "message": "MCP is currently disabled. Set SC_MCP_ENABLED=true.",
            },
        })
        return  # Exit cleanly — do not accept any requests

    # Initialise real ToolRegistry so tools/call flows through
    # ToolRegistry.execute_verified() → ToolPolicyService + ToolVerifier
    from app.api.deps import get_tool_registry

    tool_registry = get_tool_registry()
    default_user_id = _resolve_default_user_id()

    adapter = create_default_adapter(tool_registry=tool_registry)
    logger.info(
        "MCP Server ready (stdio mode). Safe tools: %s, default_user: %s",
        sorted(MCP_SAFE_TOOLS),
        str(default_user_id) if default_user_id else "not configured",
    )

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON received")
            continue

        try:
            response = handle_request(request, adapter, default_user_id)
            if response is not None:
                _send(response)
        except Exception:
            logger.exception("Error handling request")


if __name__ == "__main__":
    run_stdio()
