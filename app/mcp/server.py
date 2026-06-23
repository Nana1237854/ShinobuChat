"""Compatibility wrapper.

New code should import from:
    app.domains.mcp.server
"""

from app.domains.mcp.server import *

if __name__ == "__main__":
    from app.domains.mcp.server import run_stdio
    run_stdio()