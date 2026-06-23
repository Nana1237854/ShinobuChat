"""MCP Adapter configuration (F14.5)."""

import os

MCP_ENABLED = os.getenv("SC_MCP_ENABLED", "false").lower() == "true"
MCP_DEFAULT_USER_ID = os.getenv("SC_MCP_DEFAULT_USER_ID", "")
MCP_TOKEN = os.getenv("SC_MCP_TOKEN", "")

# Tool allowlist for MCP exposure
MCP_SAFE_TOOLS = {
    "open_local_app",
    "open_url",
    "read_webpage",
    "search_web",
}

MCP_BLOCKED_TOOLS = {
    "shell_command",
    "browser_click",
    "download_file",
    "run_installer",
    "file_write",
}
