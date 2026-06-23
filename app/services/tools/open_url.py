"""ToolRegistry tool: open_url — open a public URL after safety + permission checks."""

import json

from app.domains.browser.browser_automation_service import BrowserAutomationService
from app.domains.local_agent.local_agent_settings_service import LocalAgentSettingsService
from app.services.tool_registry import Tool, ToolContext


def create_tool(registry) -> Tool:
    def handler(arguments: dict, context: ToolContext) -> str:
        url = str(arguments.get("url", ""))

        # F16: permission gate — Browser Reader must be enabled
        if registry.session_factory and context.user_id:
            db = registry.session_factory()
            try:
                LocalAgentSettingsService(db).ensure_browser_reader_enabled(context.user_id)
            finally:
                db.close()

        result = BrowserAutomationService().open_url(url, user_id=context.user_id)
        return json.dumps(result, ensure_ascii=False)

    return Tool(
        name="open_url",
        description="Open a public URL in the default browser after URL safety validation.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
            },
            "required": ["url"],
        },
        handler=handler,
    )
