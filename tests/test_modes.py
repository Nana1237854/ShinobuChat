import uuid
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.user import User
from app.schemas.mode import (
    ConversationMode,
    ConversationModeUpdate,
)
from app.services.mode_service import (
    DECISION_TENDENCIES,
    REMINDER_POLICIES,
    REPLY_POLICIES,
    ROLEPLAY_PROMPT_SECTIONS,
    TOOL_POLICIES,
    ModeService,
)


class ModeServiceCRUDTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="m@t.com", hashed_password="x", display_name="M"))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _svc(self) -> ModeService:
        return ModeService(self.Session())

    # ── CRUD ──

    def test_default_mode_is_companion(self):
        resp = self._svc().get_settings(self.user_id)
        self.assertEqual(resp.mode, ConversationMode.COMPANION)
        self.assertEqual(resp.mode_label, "陪伴")
        self.assertIsNotNone(resp.description)
        self.assertIsNotNone(resp.behavior)

    def test_update_mode_to_work(self):
        svc = self._svc()
        updated = svc.update_settings(
            self.user_id, ConversationModeUpdate(mode=ConversationMode.WORK)
        )
        self.assertEqual(updated.mode, ConversationMode.WORK)
        self.assertEqual(updated.mode_label, "工作")
        reloaded = svc.get_settings(self.user_id)
        self.assertEqual(reloaded.mode, ConversationMode.WORK)

    def test_update_all_four_modes(self):
        svc = self._svc()
        for mode in ConversationMode:
            updated = svc.update_settings(self.user_id, ConversationModeUpdate(mode=mode))
            self.assertEqual(updated.mode, mode)
            self.assertTrue(len(updated.mode_label) > 0)

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            ConversationMode("invalid")

    def test_cross_user_isolation(self):
        other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=other_id, email="b@t.com", hashed_password="x", display_name="B"))
            db.commit()
        svc = self._svc()
        svc.update_settings(self.user_id, ConversationModeUpdate(mode=ConversationMode.FOCUS))
        other_settings = svc.get_settings(other_id)
        self.assertEqual(other_settings.mode, ConversationMode.COMPANION)

    def test_get_mode_shortcut(self):
        svc = self._svc()
        mode = svc.get_mode(self.user_id)
        self.assertEqual(mode, ConversationMode.COMPANION)
        svc.update_settings(self.user_id, ConversationModeUpdate(mode=ConversationMode.NIGHT))
        self.assertEqual(svc.get_mode(self.user_id), ConversationMode.NIGHT)

    # ── Behavior ──

    def test_behavior_returns_all_policies(self):
        behavior = self._svc().get_mode_behavior(self.user_id)
        self.assertIsNotNone(behavior.tool_policy)
        self.assertIsNotNone(behavior.reply_policy)
        self.assertIsNotNone(behavior.reminder_policy)
        self.assertIsNotNone(behavior.decision_tendency)

    def test_behavior_changes_with_mode(self):
        svc = self._svc()
        companion_behavior = svc.get_mode_behavior(self.user_id)
        svc.update_settings(self.user_id, ConversationModeUpdate(mode=ConversationMode.WORK))
        work_behavior = svc.get_mode_behavior(self.user_id)
        self.assertNotEqual(
            companion_behavior.decision_tendency.agent_weight,
            work_behavior.decision_tendency.agent_weight,
        )

    # ── Prompt sections ──

    def test_companion_prompt_section_is_empty(self):
        self.assertEqual(
            self._svc().build_roleplay_prompt_section("companion"), ""
        )

    def test_work_prompt_section_has_structure(self):
        section = self._svc().build_roleplay_prompt_section("work")
        self.assertIn("结构化", section)
        self.assertIn("结论", section)

    def test_focus_prompt_section_suppresses_chat(self):
        section = self._svc().build_roleplay_prompt_section("focus")
        self.assertIn("不主动闲聊", section)

    def test_night_prompt_section_is_quiet(self):
        section = self._svc().build_roleplay_prompt_section("night")
        self.assertIn("轻柔", section)

    def test_unknown_mode_returns_empty_prompt(self):
        self.assertEqual(
            self._svc().build_roleplay_prompt_section("nonexistent"), ""
        )

    # ── Tool policies ──

    def test_companion_tool_policy_blocks_shell(self):
        policy = self._svc().get_tool_policy("companion")
        self.assertIn("shell", policy.blocked_tool_groups)

    def test_focus_tool_policy_restricted(self):
        policy = self._svc().get_tool_policy("focus")
        self.assertNotIn("shell", policy.allowed_tool_groups)
        self.assertNotIn("web_search", policy.allowed_tool_groups)

    def test_work_tool_policy_allows_tasks(self):
        policy = self._svc().get_tool_policy("work")
        self.assertIn("todo", policy.allowed_tool_groups)

    def test_unknown_mode_falls_back_to_companion_tool_policy(self):
        policy = self._svc().get_tool_policy("nonexistent")
        self.assertIn("chat", policy.allowed_tool_groups)

    # ── Reply policies ──

    def test_companion_reply_natural(self):
        policy = self._svc().get_reply_policy("companion")
        self.assertEqual(policy.style, "natural")
        self.assertFalse(policy.prioritize_conciseness)

    def test_work_reply_structured(self):
        policy = self._svc().get_reply_policy("work")
        self.assertEqual(policy.style, "structured")
        self.assertTrue(policy.prioritize_conciseness)

    def test_focus_reply_minimal(self):
        policy = self._svc().get_reply_policy("focus")
        self.assertEqual(policy.max_sentences, 1)

    def test_night_reply_soft(self):
        policy = self._svc().get_reply_policy("night")
        self.assertEqual(policy.style, "soft")

    # ── Reminder policies ──

    def test_companion_reminder_friendly(self):
        policy = self._svc().get_reminder_policy("companion")
        self.assertTrue(policy.enabled)
        self.assertFalse(policy.reduce_frequency)
        self.assertEqual(policy.tone, "friendly")

    def test_focus_reminder_urgent_only(self):
        policy = self._svc().get_reminder_policy("focus")
        self.assertTrue(policy.urgent_only)
        self.assertTrue(policy.reduce_frequency)

    def test_night_reminder_quiet(self):
        policy = self._svc().get_reminder_policy("night")
        self.assertEqual(policy.tone, "quiet")

    def test_work_reminder_task_oriented(self):
        policy = self._svc().get_reminder_policy("work")
        self.assertEqual(policy.tone, "task_oriented")

    # ── Decision tendencies ──

    def test_companion_prefers_chat(self):
        tendency = self._svc().get_decision_tendency("companion")
        self.assertGreater(tendency.chat_weight, tendency.agent_weight)

    def test_work_prefers_agent(self):
        tendency = self._svc().get_decision_tendency("work")
        self.assertGreater(tendency.agent_weight, tendency.chat_weight)
        self.assertTrue(tendency.prefer_todo_create)

    def test_focus_suppresses_idle_chat(self):
        tendency = self._svc().get_decision_tendency("focus")
        self.assertTrue(tendency.suppress_idle_chat)

    def test_night_suppresses_idle_chat(self):
        tendency = self._svc().get_decision_tendency("night")
        self.assertTrue(tendency.suppress_idle_chat)

    # ── Policy table completeness ──

    def test_all_four_modes_have_tool_policy(self):
        for mode in ConversationMode:
            self.assertIn(mode.value, TOOL_POLICIES)

    def test_all_four_modes_have_reply_policy(self):
        for mode in ConversationMode:
            self.assertIn(mode.value, REPLY_POLICIES)

    def test_all_four_modes_have_reminder_policy(self):
        for mode in ConversationMode:
            self.assertIn(mode.value, REMINDER_POLICIES)

    def test_all_four_modes_have_decision_tendency(self):
        for mode in ConversationMode:
            self.assertIn(mode.value, DECISION_TENDENCIES)

    def test_all_four_modes_have_prompt_section(self):
        for mode in ConversationMode:
            self.assertIn(mode.value, ROLEPLAY_PROMPT_SECTIONS)

    # ── Response shape ──

    def test_response_includes_mode_label(self):
        resp = self._svc().get_settings(self.user_id)
        self.assertEqual(resp.mode_label, "陪伴")
        svc = self._svc()
        svc.update_settings(self.user_id, ConversationModeUpdate(mode=ConversationMode.WORK))
        resp2 = svc.get_settings(self.user_id)
        self.assertEqual(resp2.mode_label, "工作")

    def test_response_includes_description(self):
        resp = self._svc().get_settings(self.user_id)
        self.assertIn("陪伴", resp.description)

    def test_response_includes_updated_at(self):
        resp = self._svc().get_settings(self.user_id)
        self.assertIsNotNone(resp.updated_at)
