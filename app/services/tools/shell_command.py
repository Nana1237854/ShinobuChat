import shlex
import subprocess

from app.core.config import settings
from app.services.tool_registry import Tool, ToolContext


def create_tool(registry) -> Tool:
    def handler(arguments: dict, context: ToolContext) -> str:
        command = str(arguments.get("command", ""))
        if any(token in command for token in ("|", "&", ";", ">", "<", "`", "$(")):
            return "Rejected: shell control operators are not allowed."

        try:
            parts = shlex.split(command, posix=False)
        except ValueError as exc:
            return f"Rejected: could not parse command: {exc}"

        if not parts or parts[0].lower() not in {"curl", "curl.exe"}:
            return "Rejected: only curl/curl.exe commands are allowed."

        timeout_seconds = min(settings.ai_request_timeout_seconds, 30)
        try:
            completed = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout_seconds} seconds."
        except OSError as exc:
            return f"Command failed to start: {exc}"

        output = (completed.stdout or completed.stderr or "").strip()
        return output[:12000] or f"Command exited with code {completed.returncode} and no output."

    return Tool(
        name="shell_command",
        description="Run a restricted read-only shell command. Only curl/curl.exe requests are allowed.",
        parameters={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
        handler=handler,
    )
