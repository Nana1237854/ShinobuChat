import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.skill_service import SkillRegistry
from app.services.tool_registry import ToolContext, ToolRegistry


class ToolRegistryShellCommandTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry(SkillRegistry(Path("skills")))
        self.context = ToolContext(history=[])

    def test_shell_command_returns_timeout_result(self):
        with patch(
            "app.services.tools.shell_command.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["curl", "http://example.com"], timeout=30),
        ):
            result = self.registry.execute(
                "shell_command",
                {"command": "curl http://example.com"},
                self.context,
            )

        self.assertEqual(result, "Command timed out after 30 seconds.")

    def test_shell_command_returns_startup_error_result(self):
        with patch(
            "app.services.tools.shell_command.subprocess.run",
            side_effect=OSError("curl not found"),
        ):
            result = self.registry.execute(
                "shell_command",
                {"command": "curl http://example.com"},
                self.context,
            )

        self.assertEqual(result, "Command failed to start: curl not found")


if __name__ == "__main__":
    unittest.main()
