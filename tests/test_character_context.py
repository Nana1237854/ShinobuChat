"""Tests for B16: Group Characters Context Injection."""

import uuid
import unittest
from unittest.mock import MagicMock, patch


class CharacterContextTests(unittest.TestCase):
    """Test AgentCoordinator._conversation_characters_context behaviour."""

    def setUp(self):
        self.user_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()

    # ── Guard phrases ──

    def test_context_includes_anti_self_chat_guard_phrases(self):
        """Context string must include all required guard phrases."""
        mock_session = MagicMock()
        with patch(
            "app.db.session.SessionLocal", return_value=mock_session
        ):
            from app.services.agents.coordinator import AgentCoordinator

            _names, context = AgentCoordinator._conversation_characters_context(
                self.user_id, None
            )

        self.assertIn("Shinobu 是主要角色(primary)，始终优先回复。", context)
        self.assertIn("辅助角色只能提供简短补充，每个最多一句话。", context)
        self.assertIn("辅助角色之间不得互相继续对话。", context)
        self.assertIn("辅助角色内容不得写入长期记忆。", context)

    def test_context_fallback_when_no_conversation_id(self):
        """When conversation_id is None, context still includes Shinobu as primary."""
        mock_session = MagicMock()
        with patch(
            "app.db.session.SessionLocal", return_value=mock_session
        ):
            from app.services.agents.coordinator import AgentCoordinator

            names, context = AgentCoordinator._conversation_characters_context(
                self.user_id, None
            )

        self.assertEqual(names, ["Shinobu"])
        self.assertIn("Shinobu 是主要角色(primary)", context)

    def test_shinobu_is_always_primary(self):
        """Shinobu is always the first name returned and marked as primary."""
        mock_session = MagicMock()
        with patch(
            "app.db.session.SessionLocal", return_value=mock_session
        ):
            from app.services.agents.coordinator import AgentCoordinator

            names, context = AgentCoordinator._conversation_characters_context(
                self.user_id, self.conversation_id
            )

        # Shinobu is always the first entry
        self.assertGreaterEqual(len(names), 1)
        self.assertEqual(names[0], "Shinobu")
        self.assertIn("primary", context)

    def test_fallback_when_exception_occurs(self):
        """When an unexpected exception occurs, graceful fallback still returns Shinobu."""
        with patch(
            "app.db.session.SessionLocal",
            side_effect=RuntimeError("Simulated DB failure"),
        ):
            from app.services.agents.coordinator import AgentCoordinator

            names, context = AgentCoordinator._conversation_characters_context(
                self.user_id, self.conversation_id
            )

        # Should still return Shinobu-only context despite the exception
        self.assertEqual(names, ["Shinobu"])
        self.assertIn("Shinobu 是主要角色(primary)", context)
        self.assertIn("辅助角色内容不得写入长期记忆。", context)
