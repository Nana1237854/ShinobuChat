import unittest

from app.services.tool_policy_service import ToolPolicyDecision, ToolPolicyService


class ToolPolicyServiceTests(unittest.TestCase):
    def setUp(self):
        self.svc = ToolPolicyService()

    def _check(self, tool: str, mode: str = "companion", route: str = "agent"):
        return self.svc.check(tool, {}, conversation_mode=mode, route_mode=route)

    # ── Always-denied tools ──

    def test_shell_command_denied_in_all_modes(self):
        for mode in ("companion", "work", "focus", "night"):
            decision = self._check("shell_command", mode)
            self.assertFalse(decision.allowed, f"shell_command should be denied in {mode}")
            self.assertIn("blocked", decision.reason)

    def test_shell_denied(self):
        decision = self._check("shell")
        self.assertFalse(decision.allowed)

    def test_exec_denied(self):
        decision = self._check("exec")
        self.assertFalse(decision.allowed)

    def test_file_delete_denied(self):
        decision = self._check("file_delete")
        self.assertFalse(decision.allowed)

    # ── Mode-aware group checks ──

    def test_todo_create_allowed_in_work(self):
        decision = self._check("todo_create", "work")
        self.assertTrue(decision.allowed)
        self.assertIn("todo", decision.reason)

    def test_fetch_web_page_allowed_in_work(self):
        decision = self._check("fetch_web_page", "work")
        self.assertTrue(decision.allowed)

    def test_fetch_web_page_denied_in_companion(self):
        decision = self._check("fetch_web_page", "companion")
        self.assertFalse(decision.allowed)

    def test_fetch_web_page_denied_in_focus(self):
        decision = self._check("fetch_web_page", "focus")
        self.assertFalse(decision.allowed)

    # ── Focus mode suppression ──

    def test_focus_blocks_chat_tools(self):
        decision = self._check("chat", "focus")
        self.assertFalse(decision.allowed)
        self.assertIn("focus", decision.reason.lower())

    # ── Night mode suppression ──

    def test_night_blocks_todo_tools(self):
        decision = self._check("todo_create", "night")
        self.assertFalse(decision.allowed)
        self.assertIn("night", decision.reason.lower())

    def test_night_blocks_goal_tools(self):
        decision = self._check("goal_create", "night")
        self.assertFalse(decision.allowed)

    # ── Allowed tools ──

    def test_todo_create_allowed_in_companion(self):
        decision = self._check("todo_create", "companion")
        self.assertTrue(decision.allowed)

    def test_conversation_digest_allowed_in_companion(self):
        decision = self._check("conversation_digest", "companion")
        self.assertTrue(decision.allowed)

    def test_reminder_allowed_in_all_modes(self):
        for mode in ("companion", "work", "focus", "night"):
            decision = self._check("reminder_scan", mode)
            self.assertTrue(decision.allowed, f"reminder_scan should be allowed in {mode}")

    # ── Checked fields ──

    def test_denied_checked_fields_contain_rule(self):
        decision = self._check("shell_command")
        self.assertEqual(decision.checked_fields.get("rule"), "always_denied")

    def test_allowed_checked_fields_contain_tool_group(self):
        decision = self._check("todo_create", "work")
        self.assertIn("tool_group", decision.checked_fields)

    def test_allowed_checked_fields_contain_conversation_mode(self):
        decision = self._check("todo_create", "work")
        self.assertEqual(decision.checked_fields.get("conversation_mode"), "work")

    # ── Unknown mode fallback ──

    def test_unknown_mode_falls_back_to_companion(self):
        decision = self._check("chat", "nonexistent")
        self.assertTrue(decision.allowed)

    # ── test: policy.allowed -> handler not called (integration) ──
    # This verifies that when execute_verified is the integration point,
    # a denied policy returns verified=False BEFORE any handler call.
    # We test this in test_tool_registry below.


class ToolRegistryPolicyGateTests(unittest.TestCase):
    """Verify that ToolRegistry.execute_verified enforces tool policy before execution."""

    def setUp(self):
        self.handler_called = False

        def fake_handler(args, ctx):
            self.handler_called = True
            return '{"status": "ok"}'

        from unittest.mock import MagicMock

        self.mock_skill_registry = MagicMock()
        self.mock_client = MagicMock()
        from app.services.tool_registry import Tool, ToolContext, ToolRegistry

        self.registry = ToolRegistry(self.mock_skill_registry, self.mock_client)
        self.tool = Tool(
            name="shell_command",
            description="Execute shell",
            parameters={},
            handler=fake_handler,
        )
        self.registry._tools["shell_command"] = self.tool

        # Also add a safe tool
        self.safe_tool = Tool(
            name="todo_create",
            description="Create a todo",
            parameters={},
            handler=fake_handler,
        )
        self.registry._tools["todo_create"] = self.safe_tool

    def test_denied_tool_does_not_call_handler(self):
        ctx = type("Ctx", (), {"metadata": {"conversation_mode": "companion", "route_mode": "agent"}})()
        result = self.registry.execute_verified("shell_command", {}, ctx)
        self.assertFalse(result.verified)
        self.assertIn("Tool policy denied", result.reason)
        self.assertFalse(self.handler_called, "Handler must NOT be called when policy denies")

    def test_allowed_tool_calls_handler_and_verifies(self):
        ctx = type("Ctx", (), {"metadata": {"conversation_mode": "work", "route_mode": "agent"}})()
        result = self.registry.execute_verified("todo_create", {}, ctx)
        self.assertTrue(self.handler_called, "Handler SHOULD be called when policy allows")
        self.assertIn("policy_allowed", result.checked_fields)
        self.assertTrue(result.checked_fields.get("policy_allowed"))

    def test_denied_result_has_policy_allowed_false(self):
        ctx = type("Ctx", (), {"metadata": {"conversation_mode": "companion"}})()
        result = self.registry.execute_verified("shell_command", {}, ctx)
        self.assertEqual(result.checked_fields.get("policy_allowed"), False)
        self.assertEqual(result.checked_fields.get("conversation_mode"), "companion")
