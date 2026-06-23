import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from app.services.tool_registry import ToolContext


class ToolContextMetadataTests(unittest.TestCase):
    """Test ToolContext dataclass with user_id and conversation_id fields."""

    def setUp(self):
        self.user_id = uuid4()
        self.conversation_id = uuid4()

    def test_tool_context_with_user_id_and_conversation_id(self):
        ctx = ToolContext(
            history=[],
            user_id=self.user_id,
            conversation_id=self.conversation_id,
        )
        self.assertEqual(ctx.user_id, self.user_id)
        self.assertEqual(ctx.conversation_id, self.conversation_id)

    def test_tool_context_backward_compat_without_ids(self):
        """Omitting user_id/conversation_id must still work (backward compat)."""
        ctx = ToolContext(history=[])
        self.assertIsNone(ctx.user_id)
        self.assertIsNone(ctx.conversation_id)

    def test_tool_context_with_metadata_and_ids(self):
        ctx = ToolContext(
            history=[],
            user_skills={"test": MagicMock()},
            metadata={"conversation_mode": "companion", "route_mode": "agent"},
            user_id=self.user_id,
            conversation_id=self.conversation_id,
        )
        self.assertEqual(ctx.user_id, self.user_id)
        self.assertEqual(ctx.conversation_id, self.conversation_id)
        self.assertEqual(ctx.metadata["conversation_mode"], "companion")
        self.assertEqual(ctx.metadata["route_mode"], "agent")

    def test_tool_context_frozen_immutable(self):
        """ToolContext must remain a frozen dataclass."""
        ctx = ToolContext(history=[], user_id=self.user_id)
        with self.assertRaises(Exception):
            ctx.user_id = uuid4()  # type: ignore[misc]

    def test_tool_context_with_none_ids_explicit(self):
        ctx = ToolContext(
            history=[],
            user_id=None,
            conversation_id=None,
        )
        self.assertIsNone(ctx.user_id)
        self.assertIsNone(ctx.conversation_id)

    def test_tool_context_accepts_uuid_str_coercion(self):
        """ToolContext fields accept UUID objects."""
        uid = UUID("12345678-1234-5678-1234-567812345678")
        cid = UUID("87654321-4321-8765-4321-876543218765")
        ctx = ToolContext(history=[], user_id=uid, conversation_id=cid)
        self.assertEqual(ctx.user_id, uid)
        self.assertEqual(ctx.conversation_id, cid)


class AgentOrchestratorToolContextPassThroughTests(unittest.TestCase):
    """Test that AgentOrchestrator.run() writes user_id/conversation_id to ToolContext."""

    def test_run_passes_user_id_and_conversation_id_to_tool_context(self):
        from app.services.agent_orchestrator import AgentOrchestrator

        mock_agent_svc = MagicMock()
        mock_tool_registry = MagicMock()
        mock_ai_client = MagicMock()

        # Setup AI client to return a message without tool calls (quick exit after one step)
        mock_ai_client.complete_chat.return_value = {
            "content": "Hello, I am your assistant.",
            "tool_calls": [],
        }

        mock_tool_registry.schemas.return_value = []

        orchestrator = AgentOrchestrator(
            agent_service=mock_agent_svc,
            tool_registry=mock_tool_registry,
            ai_client=mock_ai_client,
        )

        user_id = uuid4()
        conversation_id = uuid4()

        # Intercept ToolContext construction by replacing __init__
        original_init = ToolContext.__init__
        captured_contexts = []

        def _capturing_init(self, **kwargs):
            captured_contexts.append(dict(kwargs))
            original_init(self, **kwargs)

        with patch.object(ToolContext, "__init__", _capturing_init):
            list(orchestrator.run(
                messages=[{"role": "user", "content": "Hi"}],
                history=[],
                user_id=user_id,
                conversation_id=conversation_id,
            ))

        self.assertGreater(len(captured_contexts), 0,
                          "ToolContext should have been constructed at least once")

        ctx_kwargs = captured_contexts[0]
        self.assertEqual(ctx_kwargs.get("user_id"), user_id,
                        "ToolContext should receive user_id")
        self.assertEqual(ctx_kwargs.get("conversation_id"), conversation_id,
                        "ToolContext should receive conversation_id")

    def test_run_omits_ids_for_backward_compat(self):
        """When user_id/conversation_id are not provided, ToolContext gets None."""
        from app.services.agent_orchestrator import AgentOrchestrator

        mock_agent_svc = MagicMock()
        mock_tool_registry = MagicMock()
        mock_ai_client = MagicMock()
        mock_ai_client.complete_chat.return_value = {
            "content": "Hello.",
            "tool_calls": [],
        }
        mock_tool_registry.schemas.return_value = []

        orchestrator = AgentOrchestrator(
            agent_service=mock_agent_svc,
            tool_registry=mock_tool_registry,
            ai_client=mock_ai_client,
        )

        original_init = ToolContext.__init__
        captured_contexts = []

        def _capturing_init(self, **kwargs):
            captured_contexts.append(dict(kwargs))
            original_init(self, **kwargs)

        with patch.object(ToolContext, "__init__", _capturing_init):
            list(orchestrator.run(
                messages=[{"role": "user", "content": "Hi"}],
                history=[],
            ))

        self.assertGreater(len(captured_contexts), 0)
        ctx_kwargs = captured_contexts[0]
        self.assertIsNone(ctx_kwargs.get("user_id"),
                          "ToolContext user_id should be None when not provided")
        self.assertIsNone(ctx_kwargs.get("conversation_id"),
                          "ToolContext conversation_id should be None when not provided")


if __name__ == "__main__":
    unittest.main()
