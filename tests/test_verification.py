import json
import tempfile
import uuid
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.memory import Memory
from app.models.todo import Todo
from app.models.user import User
from app.models.user_config import UserConfig
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.skill_service import Skill, SkillRegistry
from app.services.stream_events import StreamEvent
from app.services.tool_policy_service import ToolPolicyDecision
from app.services.tool_registry import ToolContext, ToolRegistry
from app.services.tool_verifier import ToolVerifier, VerificationResult


class VerificationResultTests(unittest.TestCase):
    def test_ok_is_alias_for_passed(self):
        vr = VerificationResult(True, "all good")
        self.assertTrue(vr.ok)
        self.assertTrue(vr.passed)

        vr_fail = VerificationResult(False, "bad")
        self.assertFalse(vr_fail.ok)
        self.assertFalse(vr_fail.passed)

    def test_checked_fields_and_tool_name_are_stored(self):
        vr = VerificationResult(
            True,
            "ok",
            tool_name="shell_command",
            checked_fields={"exit_code": 0},
        )
        self.assertEqual(vr.tool_name, "shell_command")
        self.assertEqual(vr.checked_fields, {"exit_code": 0})


class ToolVerifierGenericTests(unittest.TestCase):
    def setUp(self):
        self.verifier = ToolVerifier()
        self.context = ToolContext(history=[])

    def test_empty_result_fails(self):
        result = self.verifier.verify("any_tool", "", {}, self.context)
        self.assertFalse(result.ok)
        self.assertIn("empty", result.reason)
        self.assertTrue(result.checked_fields.get("result_empty"))

    def test_result_whitespace_only_fails(self):
        result = self.verifier.verify("any_tool", "   \n  ", {}, self.context)
        self.assertFalse(result.ok)
        self.assertIn("empty", result.reason)

    def test_error_prefix_fails(self):
        result = self.verifier.verify("any_tool", "ERROR: something went wrong", {}, self.context)
        self.assertFalse(result.ok)
        self.assertIn("ERROR:", result.reason)
        self.assertTrue(result.checked_fields.get("starts_with_error"))

    def test_json_error_payload_fails(self):
        result = self.verifier.verify(
            "any_tool",
            json.dumps({"error": "not found"}),
            {},
            self.context,
        )
        self.assertFalse(result.ok)
        self.assertIn("error payload", result.reason)

    def test_json_status_error_fails(self):
        result = self.verifier.verify(
            "any_tool",
            json.dumps({"status": "error", "message": "fail"}),
            {},
            self.context,
        )
        self.assertFalse(result.ok)

    def test_failure_keyword_fails(self):
        result = self.verifier.verify("any_tool", "Command failed: connection refused", {}, self.context)
        self.assertFalse(result.ok)
        self.assertTrue(result.checked_fields.get("has_failure_marker"))

    def test_valid_non_json_result_passes(self):
        result = self.verifier.verify("any_tool", "Successfully completed", {}, self.context)
        self.assertTrue(result.ok)
        self.assertEqual(result.tool_name, "any_tool")
        self.assertFalse(result.checked_fields.get("is_json"))


class ShellCommandVerificationTests(unittest.TestCase):
    def setUp(self):
        self.verifier = ToolVerifier()

    def test_exit_code_zero_passes(self):
        context = ToolContext(history=[])
        context.metadata["exit_code"] = 0
        result = self.verifier.verify("shell_command", "some output", {}, context)
        self.assertTrue(result.ok)
        self.assertEqual(result.checked_fields.get("exit_code"), 0)

    def test_exit_code_nonzero_fails(self):
        context = ToolContext(history=[])
        context.metadata["exit_code"] = 22
        result = self.verifier.verify("shell_command", "error output", {}, context)
        self.assertFalse(result.ok)
        self.assertIn("code 22", result.reason)

    def test_missing_exit_code_fails(self):
        context = ToolContext(history=[])
        result = self.verifier.verify("shell_command", "output", {}, context)
        self.assertFalse(result.ok)
        self.assertIn("did not report an exit code", result.reason)


class WriteFileVerificationTests(unittest.TestCase):
    def setUp(self):
        self.verifier = ToolVerifier()

    def test_file_exists_passes(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello")
            file_path = f.name

        try:
            context = ToolContext(history=[])
            result = self.verifier.verify(
                "write_file",
                "file written",
                {"file_path": file_path},
                context,
            )
            self.assertTrue(result.ok)
            self.assertTrue(result.checked_fields.get("file_exists"))
        finally:
            Path(file_path).unlink()

    def test_file_not_found_fails(self):
        context = ToolContext(history=[])
        result = self.verifier.verify(
            "write_file",
            "file written",
            {"file_path": "/nonexistent/path/file.txt"},
            context,
        )
        self.assertFalse(result.ok)
        self.assertIn("does not exist", result.reason)
        self.assertFalse(result.checked_fields.get("file_exists"))

    def test_no_file_path_argument_fails(self):
        context = ToolContext(history=[])
        result = self.verifier.verify("write_file", "done", {}, context)
        self.assertFalse(result.ok)
        self.assertIn("no file_path", result.reason)

    def test_edit_file_uses_same_check(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            file_path = f.name

        try:
            context = ToolContext(history=[])
            result = self.verifier.verify(
                "edit_file",
                "edited",
                {"file_path": file_path},
                context,
            )
            self.assertTrue(result.ok)
        finally:
            Path(file_path).unlink()


class TodoCreateVerificationTests(unittest.TestCase):
    def setUp(self):
        self.verifier = ToolVerifier()

    def test_result_with_valid_todo_id_passes(self):
        todo_id = str(uuid.uuid4())
        context = ToolContext(history=[])
        result = self.verifier.verify(
            "todo_create",
            json.dumps({"id": todo_id, "title": "test todo"}),
            {},
            context,
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.checked_fields.get("result_has_todo_id"))
        self.assertTrue(result.checked_fields.get("todo_id_valid_uuid"))

    def test_result_with_todo_id_field_passes(self):
        todo_id = str(uuid.uuid4())
        context = ToolContext(history=[])
        result = self.verifier.verify(
            "todo_create",
            json.dumps({"todo_id": todo_id}),
            {},
            context,
        )
        self.assertTrue(result.ok)

    def test_result_without_todo_id_fails(self):
        context = ToolContext(history=[])
        result = self.verifier.verify(
            "todo_create",
            json.dumps({"message": "created"}),
            {},
            context,
        )
        self.assertFalse(result.ok)
        self.assertIn("no valid todo id", result.reason)

    def test_invalid_uuid_in_result_fails(self):
        context = ToolContext(history=[])
        result = self.verifier.verify(
            "todo_create",
            json.dumps({"id": "not-a-uuid"}),
            {},
            context,
        )
        self.assertFalse(result.ok)

    def test_non_json_result_fails(self):
        context = ToolContext(history=[])
        result = self.verifier.verify("todo_create", "created successfully", {}, context)
        self.assertFalse(result.ok)

    def test_todo_in_db_with_session_factory(self):
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, future=True)

        todo_id = uuid.uuid4()
        user_id_val = uuid.uuid4()

        with Session() as db:
            db.add(User(
                id=user_id_val,
                email="test@example.com",
                hashed_password="x",
                display_name="Test",
            ))
            db.add(Todo(
                id=todo_id,
                user_id=user_id_val,
                title="test todo",
            ))
            db.commit()

        verifier = ToolVerifier(session_factory=Session)
        context = ToolContext(history=[])
        result = verifier.verify(
            "todo_create",
            json.dumps({"id": str(todo_id)}),
            {},
            context,
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.checked_fields.get("todo_in_db"))

        Base.metadata.drop_all(bind=engine)


class MemoryStoreVerificationTests(unittest.TestCase):
    def setUp(self):
        self.verifier = ToolVerifier()

    def test_result_with_valid_memory_id_passes(self):
        memory_id = str(uuid.uuid4())
        context = ToolContext(history=[])
        result = self.verifier.verify(
            "memory_store",
            json.dumps({"id": memory_id, "content": "remembered item"}),
            {},
            context,
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.checked_fields.get("result_has_memory_id"))
        self.assertTrue(result.checked_fields.get("memory_id_valid_uuid"))

    def test_result_without_memory_id_fails(self):
        context = ToolContext(history=[])
        result = self.verifier.verify(
            "memory_store",
            json.dumps({"stored": True}),
            {},
            context,
        )
        self.assertFalse(result.ok)
        self.assertIn("no valid memory id", result.reason)


class SkillInstallVerificationTests(unittest.TestCase):
    def setUp(self):
        self.verifier = ToolVerifier()

    def test_skill_found_in_context_passes(self):
        skill = Skill(
            name="test-skill",
            description="A test skill",
            content="# Test",
            keywords=("test",),
        )
        context = ToolContext(
            history=[],
            user_skills={"test-skill": skill},
        )
        result = self.verifier.verify(
            "skill_install",
            json.dumps({"name": "test-skill", "installed": True}),
            {"name": "test-skill"},
            context,
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.checked_fields.get("skill_in_user_context"))

    def test_skill_not_found_fails(self):
        context = ToolContext(history=[], user_skills={})
        result = self.verifier.verify(
            "skill_install",
            json.dumps({"name": "nonexistent"}),
            {"name": "nonexistent"},
            context,
        )
        self.assertFalse(result.ok)
        self.assertFalse(result.checked_fields.get("skill_in_user_context"))

    def test_no_skill_name_fails(self):
        context = ToolContext(history=[])
        result = self.verifier.verify("skill_install", "installed", {}, context)
        self.assertFalse(result.ok)
        self.assertIn("no skill name", result.reason)


class ConfigUpdateVerificationTests(unittest.TestCase):
    def setUp(self):
        self.verifier = ToolVerifier()

    def test_config_update_without_db_soft_passes_if_no_error(self):
        context = ToolContext(history=[])
        result = self.verifier.verify(
            "config_update",
            json.dumps({"updated": True, "key": "ai_model"}),
            {"key": "ai_model", "value": "test-model"},
            context,
        )
        # Without DB, re-read not performed, but result has no error → soft pass
        self.assertTrue(result.ok)
        self.assertIn("re-read not available", result.reason)

    def test_config_update_no_key_fails(self):
        context = ToolContext(history=[])
        result = self.verifier.verify(
            "config_update",
            json.dumps({"updated": True}),
            {},
            context,
        )
        self.assertFalse(result.ok)
        self.assertIn("no config key", result.reason)

    def test_config_update_with_db_re_read_passes(self):
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, future=True)

        user_id_val = uuid.uuid4()
        with Session() as db:
            db.add(User(
                id=user_id_val,
                email="cfg@example.com",
                hashed_password="x",
                display_name="Cfg",
            ))
            db.add(UserConfig(
                user_id=user_id_val,
                field_name="ai_model",
                field_value='"test-model"',
                encrypted=False,
            ))
            db.commit()

        verifier = ToolVerifier(session_factory=Session)
        context = ToolContext(history=[])
        result = verifier.verify(
            "config_update",
            json.dumps({"fields": [{"key": "ai_model", "value": "test-model"}]}),
            {"key": "ai_model", "value": "test-model"},
            context,
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.checked_fields.get("config_row_exists"))

        Base.metadata.drop_all(bind=engine)


class AgentOrchestratorVerifyStepTests(unittest.TestCase):
    def setUp(self):
        from app.services.agent_service import AgentService
        from app.services.ai_client import AIClient

        skill_registry = SkillRegistry(Path("skills"))
        self.agent_service = AgentService(skill_registry)
        self.tool_registry = ToolRegistry(skill_registry)
        self.ai_client = MagicMock(spec=AIClient)
        self.orchestrator = AgentOrchestrator(
            self.agent_service,
            self.tool_registry,
            self.ai_client,
        )

    def test_verify_step_accepts_verified_result(self):
        """verify_step takes a VerifiedToolResult and logs it (returns None)."""
        from app.services.tool_registry import VerifiedToolResult

        verified = VerifiedToolResult(
            output="all good",
            verified=True,
            reason="verification passed",
            checked_fields={"generic_passed": True},
        )
        result = self.orchestrator.verify_step("any_tool", verified)
        self.assertIsNone(result)  # No-op return, verification done by ToolRegistry

    def test_verify_step_logs_failure(self):
        """verify_step should handle failed verification without raising."""
        from app.services.tool_registry import VerifiedToolResult

        verified = VerifiedToolResult(
            output="",
            verified=False,
            reason="tool returned an empty result",
            checked_fields={"result_empty": True},
        )
        # Should not raise — just logs
        result = self.orchestrator.verify_step("any_tool", verified)
        self.assertIsNone(result)

    def test_orchestrator_yields_honest_message_on_verification_failure(self):
        """When verification fails, the orchestrator must not claim completion."""
        context = ToolContext(history=[])
        context.metadata["exit_code"] = 1  # force shell failure

        messages = [
            {
                "role": "user",
                "content": "Run curl http://example.com",
            }
        ]

        mock_response = {
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "shell_command",
                        "arguments": json.dumps({"command": "curl http://example.com"}),
                    },
                }
            ],
        }
        self.ai_client.complete_chat.return_value = mock_response

        # Mock execute to return a failed shell result
        import subprocess
        completed = type("Completed", (), {"stdout": "error", "stderr": "", "returncode": 1})()
        with patch("app.services.tools.shell_command.subprocess.run", return_value=completed):
            events = list(self.orchestrator.run(messages, []))

        # Check that an error event was yielded for verification failure
        error_events = [e for e in events if isinstance(e, StreamEvent) and e.event == "error"]
        self.assertTrue(any("TOOL_VERIFICATION_FAILED" in json.dumps(e.payload) for e in error_events))

        # Check that honest failure message was yielded
        chunk_events = [e for e in events if isinstance(e, StreamEvent) and e.event == "chunk"]
        honest_messages = [
            e.payload.get("delta", "")
            for e in chunk_events
            if "没有确认成功" in str(e.payload.get("delta", ""))
        ]
        self.assertTrue(len(honest_messages) > 0, "Should yield honest failure message")

        # Must NOT contain "已完成" or "已成功"
        all_text = " ".join(
            str(e.payload.get("delta", ""))
            for e in events
            if isinstance(e, StreamEvent) and e.event == "chunk"
        )
        self.assertNotIn("已完成", all_text)


class VerificationEndToEndTests(unittest.TestCase):
    """End-to-end verification via ToolRegistry.execute_verified."""

    def setUp(self):
        self.registry = ToolRegistry(SkillRegistry(Path("skills")))
        self._policy_patcher = patch(
            "app.services.tool_policy_service.ToolPolicyService.check",
            return_value=ToolPolicyDecision(True, "test bypass", {"rule": "test_bypass"}),
        )
        self._policy_patcher.start()

    def tearDown(self):
        self._policy_patcher.stop()

    def test_valid_result_returns_verified(self):
        context = ToolContext(history=[])
        context.metadata["exit_code"] = 0
        with patch(
            "app.services.tools.shell_command.subprocess.run",
            return_value=type("C", (), {"stdout": "OK", "stderr": "", "returncode": 0})(),
        ):
            result = self.registry.execute_verified(
                "shell_command",
                {"command": "curl http://example.com"},
                context,
            )
        self.assertTrue(result.verified)
        self.assertIn("exit code is 0", result.reason)
        self.assertTrue(result.checked_fields.get("exit_code") == 0)

    def test_error_result_returns_not_verified(self):
        context = ToolContext(history=[])
        with patch(
            "app.services.tools.shell_command.subprocess.run",
            return_value=type("C", (), {"stdout": "", "stderr": "fail", "returncode": 5})(),
        ):
            result = self.registry.execute_verified(
                "shell_command",
                {"command": "curl http://example.com"},
                context,
            )
        self.assertFalse(result.verified)
        self.assertIn("code 5", result.reason)

    def test_verifiedtoolresult_as_tool_message_includes_checked_fields(self):
        from app.services.tool_registry import VerifiedToolResult

        vr = VerifiedToolResult(
            output="done",
            verified=True,
            reason="ok",
            checked_fields={"exit_code": 0, "result_empty": False},
        )
        msg = json.loads(vr.as_tool_message())
        self.assertEqual(msg["status"], "verified")
        self.assertEqual(msg["checked_fields"], {"exit_code": 0, "result_empty": False})


if __name__ == "__main__":
    unittest.main()
