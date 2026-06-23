import json
from urllib import parse

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.core.url_validation import validate_url_safe
from app.services.http_client import HttpClientError
from app.services.tool_registry import Tool, ToolContext


def create_tool(registry) -> Tool:
    def handler(arguments: dict, context: ToolContext) -> str:
        url = str(arguments.get("url", ""))
        max_chars = int(arguments.get("max_chars") or 10000)
        parsed = parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return json.dumps({"error": "Only http(s) URLs are supported."}, ensure_ascii=False)

        try:
            validate_url_safe(url)
        except BadRequestError:
            return json.dumps({"error": "URL targets a disallowed host. Public URLs only."}, ensure_ascii=False)

        try:
            response = registry.http_client.request_bytes(
                url,
                headers={"User-Agent": "ShinobuChat/agent"},
                timeout=settings.ai_request_timeout_seconds,
                max_download_bytes=100_000,
                allow_internal_ips=False,
            )
        except HttpClientError as exc:
            return json.dumps({"error": f"Fetch failed: {exc}"}, ensure_ascii=False)

        text = response.body[: min(max_chars * 4, 100_000)].decode("utf-8", errors="replace")
        return text[:max_chars]

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
