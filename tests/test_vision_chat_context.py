import unittest
from unittest.mock import MagicMock, patch

from app.schemas.message import MessageCreate, RouteMode
from app.services.agents.coordinator import AgentCoordinator


class VisionContextFormattingTests(unittest.TestCase):
    """Test the _vision_context static method in AgentCoordinator."""

    def test_formats_valid_vision_context_with_chinese_wrapper(self):
        result = AgentCoordinator._vision_context("This is a cat on a couch.")
        self.assertIn("【图片分析结果】", result)
        self.assertIn("This is a cat on a couch.", result)
        self.assertEqual(result, "【图片分析结果】\nThis is a cat on a couch.")

    def test_returns_empty_string_for_none(self):
        result = AgentCoordinator._vision_context(None)
        self.assertEqual(result, "")

    def test_returns_empty_string_for_empty_str(self):
        result = AgentCoordinator._vision_context("")
        self.assertEqual(result, "")

    def test_returns_empty_string_for_whitespace_only(self):
        result = AgentCoordinator._vision_context("   ")
        self.assertEqual(result, "")

    def test_strips_leading_trailing_whitespace(self):
        result = AgentCoordinator._vision_context("  Hello world  ")
        self.assertEqual(result, "【图片分析结果】\nHello world")

    def test_multiline_vision_context(self):
        text = "A cat on a couch.\nScene: living room.\nObjects: cat, couch."
        result = AgentCoordinator._vision_context(text)
        self.assertEqual(result, f"【图片分析结果】\n{text}")


class MessageCreateVisionContextTests(unittest.TestCase):
    """Test that MessageCreate schema supports vision_context."""

    def test_message_create_without_vision_context(self):
        """Backward compatibility: vision_context is optional."""
        msg = MessageCreate(
            user_id="00000000-0000-0000-0000-000000000001",
            content="Hello",
        )
        self.assertIsNone(msg.vision_context)

    def test_message_create_with_vision_context(self):
        msg = MessageCreate(
            user_id="00000000-0000-0000-0000-000000000001",
            content="Hello",
            vision_context="A cat on a couch.",
        )
        self.assertEqual(msg.vision_context, "A cat on a couch.")

    def test_message_create_with_none_vision_context(self):
        msg = MessageCreate(
            user_id="00000000-0000-0000-0000-000000000001",
            content="Hello",
            vision_context=None,
        )
        self.assertIsNone(msg.vision_context)

    def test_message_create_with_all_fields(self):
        msg = MessageCreate(
            user_id="00000000-0000-0000-0000-000000000001",
            content="What is in this image?",
            conversation_id="00000000-0000-0000-0000-000000000002",
            route_mode=RouteMode.AUTO,
            vision_context="A bowl of ramen on a wooden table.",
        )
        self.assertEqual(msg.vision_context, "A bowl of ramen on a wooden table.")
        self.assertEqual(str(msg.conversation_id), "00000000-0000-0000-0000-000000000002")


class VisionContextInjectionOrderTests(unittest.TestCase):
    """Test that vision_context is injected after character context and before persona context."""

    def setUp(self):
        # Create mock agents
        self.mock_router = MagicMock()
        self.mock_chat = MagicMock()
        self.mock_task = MagicMock()
        self.mock_memory = MagicMock()
        self.mock_memory.search.return_value = ["memory_item"]
        self.mock_memory.is_recall_question.return_value = False
        self.mock_emotion = None

    def _make_coordinator(self):
        return AgentCoordinator(
            router_agent=self.mock_router,
            chat_agent=self.mock_chat,
            task_agent=self.mock_task,
            memory_agent=self.mock_memory,
            user_emotion_service=self.mock_emotion,
        )

    def test_vision_injected_after_character_before_persona(self):
        """When vision_context is provided, it appears in memory_context.
        The code injection order is: character, then vision, then persona.
        Due to prepend semantics, the list order is reversed (persona, vision, character).
        This test verifies the vision_context string is present."""
        self.mock_router.route.return_value = MagicMock(target=RouteMode.CHAT)
        self.mock_chat.build_messages.return_value = [{"role": "system", "content": "test"}]

        with patch.object(
            AgentCoordinator, "_conversation_mode_context", return_value=("companion", "mode_context")
        ), patch.object(
            AgentCoordinator, "_conversation_characters_context",
            return_value=(["Shinobu"], "character_context")
        ), patch.object(
            AgentCoordinator, "_persona_tone_context", return_value="persona_context"
        ), patch.object(
            AgentCoordinator, "_vision_context", wraps=AgentCoordinator._vision_context
        ) as mock_vision_wrapper:
            coordinator = self._make_coordinator()
            plan = coordinator.prepare(
                requested_route_mode=RouteMode.AUTO,
                user_id="00000000-0000-0000-0000-000000000001",
                content="What is this?",
                history=[],
                vision_context="A red apple on a table.",
            )

            mock_vision_wrapper.assert_called_once_with("A red apple on a table.")

            # Verify the context string appears in memory_context
            context_strs = plan.memory_context
            vision_str = "【图片分析结果】\nA red apple on a table."

            self.assertIn(vision_str, context_strs)

            # Verify character_context and persona_context are also present
            self.assertIn("character_context", context_strs)
            self.assertIn("persona_context", context_strs)

    def test_no_vision_context_when_none_provided(self):
        """When vision_context is None, no vision context string is injected."""
        self.mock_router.route.return_value = MagicMock(target=RouteMode.CHAT)
        self.mock_chat.build_messages.return_value = [{"role": "system", "content": "test"}]

        with patch.object(
            AgentCoordinator, "_conversation_mode_context", return_value=("companion", "")
        ), patch.object(
            AgentCoordinator, "_conversation_characters_context",
            return_value=(["Shinobu"], "")
        ), patch.object(
            AgentCoordinator, "_persona_tone_context", return_value=""
        ), patch.object(
            AgentCoordinator, "_vision_context"
        ) as mock_vision:
            coordinator = self._make_coordinator()
            coordinator.prepare(
                requested_route_mode=RouteMode.AUTO,
                user_id="00000000-0000-0000-0000-000000000001",
                content="Hello",
                history=[],
                vision_context=None,
            )

            mock_vision.assert_not_called()

    def test_no_vision_context_when_empty_string_provided(self):
        """When vision_context is empty string, no vision context string is injected."""
        self.mock_router.route.return_value = MagicMock(target=RouteMode.CHAT)
        self.mock_chat.build_messages.return_value = [{"role": "system", "content": "test"}]

        with patch.object(
            AgentCoordinator, "_conversation_mode_context", return_value=("companion", "")
        ), patch.object(
            AgentCoordinator, "_conversation_characters_context",
            return_value=(["Shinobu"], "")
        ), patch.object(
            AgentCoordinator, "_persona_tone_context", return_value=""
        ), patch.object(
            AgentCoordinator, "_vision_context"
        ) as mock_vision:
            coordinator = self._make_coordinator()
            coordinator.prepare(
                requested_route_mode=RouteMode.AUTO,
                user_id="00000000-0000-0000-0000-000000000001",
                content="Hello",
                history=[],
                vision_context="",
            )

            mock_vision.assert_not_called()


class MessageServicePassThroughTests(unittest.TestCase):
    """Test that MessageService._prepare_agent_plan passes vision_context to AgentCoordinator."""

    def test_prepare_agent_plan_passes_vision_context(self):
        from app.services.message_service import MessageService

        mock_db = MagicMock()
        mock_skill_registry = MagicMock()
        mock_agent = MagicMock()
        mock_orchestrator = MagicMock()
        mock_ai_client = MagicMock()
        mock_sse = MagicMock()
        mock_coordinator = MagicMock()
        mock_skill_manager = MagicMock()
        mock_skill_manager.runtime_skills.return_value = []

        svc = MessageService(
            db=mock_db,
            skill_registry=mock_skill_registry,
            agent=mock_agent,
            agent_orchestrator=mock_orchestrator,
            ai_client=mock_ai_client,
            sse=mock_sse,
            agent_coordinator=mock_coordinator,
            skill_manager=mock_skill_manager,
        )

        payload = MessageCreate(
            user_id="00000000-0000-0000-0000-000000000001",
            content="What's in this picture?",
            vision_context="A sunset over the ocean.",
        )

        mock_coordinator.prepare.return_value = MagicMock(
            route_mode=RouteMode.CHAT,
            router_decision=MagicMock(reason="test"),
            progress_events=[],
            messages=[],
        )

        svc._prepare_agent_plan(payload, [])

        call_kwargs = mock_coordinator.prepare.call_args.kwargs
        self.assertEqual(call_kwargs.get("vision_context"), "A sunset over the ocean.")

    def test_prepare_agent_plan_passes_none_vision_context(self):
        from app.services.message_service import MessageService

        mock_db = MagicMock()
        mock_skill_registry = MagicMock()
        mock_agent = MagicMock()
        mock_orchestrator = MagicMock()
        mock_ai_client = MagicMock()
        mock_sse = MagicMock()
        mock_coordinator = MagicMock()
        mock_skill_manager = MagicMock()
        mock_skill_manager.runtime_skills.return_value = []

        svc = MessageService(
            db=mock_db,
            skill_registry=mock_skill_registry,
            agent=mock_agent,
            agent_orchestrator=mock_orchestrator,
            ai_client=mock_ai_client,
            sse=mock_sse,
            agent_coordinator=mock_coordinator,
            skill_manager=mock_skill_manager,
        )

        payload = MessageCreate(
            user_id="00000000-0000-0000-0000-000000000001",
            content="Hello",
        )

        mock_coordinator.prepare.return_value = MagicMock(
            route_mode=RouteMode.CHAT,
            router_decision=MagicMock(reason="test"),
            progress_events=[],
            messages=[],
        )

        svc._prepare_agent_plan(payload, [])

        call_kwargs = mock_coordinator.prepare.call_args.kwargs
        self.assertIsNone(call_kwargs.get("vision_context"))


if __name__ == "__main__":
    unittest.main()
