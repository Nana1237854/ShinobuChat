"""MCP Server entry point (F14.5).

Run as a standalone process:
    python -m app.mcp.server

Implements a minimal MCP-compatible stdio JSON-RPC server.
Only exposes tools listed in MCP_SAFE_TOOLS.
"""

from __future__ import annotations

import json
import logging
import sys

from app.mcp.config import MCP_BLOCKED_TOOLS, MCP_ENABLED, MCP_SAFE_TOOLS
from app.mcp.tool_adapter import create_default_adapter

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-server")


def _send(response: dict) -> None:
    line = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def handle_request(request: dict, adapter) -> dict | None:
    method = request.get("method", "")
    req_id = request.get("id")

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

        arguments = params.get("arguments", {})
        result_text = adapter.call_tool(tool_name, arguments)
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
        logger.warning(
            "MCP is disabled. Set SC_MCP_ENABLED=true to enable."
        )
        # Still run but reject all tool calls
        # Actually, exit cleanly so the client knows
        _send({
            "jsonrpc": "2.0",
            "method": "log",
            "params": {"level": "warning", "message": "MCP is currently disabled."},
        })

    adapter = create_default_adapter()
    logger.info("MCP Server ready (stdio mode). Safe tools: %s", sorted(MCP_SAFE_TOOLS))

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
            response = handle_request(request, adapter)
            if response is not None:
                _send(response)
        except Exception:
            logger.exception("Error handling request")


if __name__ == "__main__":
    run_stdio()
