"""Unit tests for BehaviorEngine (Phase 3)."""

import pytest

from app.services.behavior_engine import BehaviorContext, BehaviorEngine


def make_context(mode: str = "companion", **overrides) -> BehaviorContext:
    kwargs = {
        "user_id": "test-user",
        "conversation_mode": mode,
        "local_agent_settings": {},
        **overrides,
    }
    return BehaviorContext(**kwargs)


class TestBehaviorEngine:
    def test_companion_mode_defaults(self):
        engine = BehaviorEngine()
        decision = engine.decide(make_context("companion"))

        assert decision.conversation_mode == "companion"
        assert decision.reply_length in ("short", "medium")
        assert decision.proactive_level == "normal"
        assert "chat" in decision.allowed_tool_groups
        assert decision.should_suppress_idle_chat is False
        assert decision.should_prefer_todo is False
        assert len(decision.prompt_hints) > 0

    def test_work_mode_prefers_todo_and_task_planning(self):
        engine = BehaviorEngine()
        decision = engine.decide(make_context("work"))

        assert decision.should_prefer_todo is True
        assert decision.should_prefer_task_planning is True
        assert decision.should_prefer_goal is True

    def test_focus_mode_suppresses_idle_chat(self):
        engine = BehaviorEngine()
        decision = engine.decide(make_context("focus"))

        assert decision.should_suppress_idle_chat is True
        assert decision.proactive_level == "low"
        assert "chat" in decision.blocked_tool_groups

    def test_night_mode_low_proactive_level(self):
        engine = BehaviorEngine()
        decision = engine.decide(make_context("night"))

        assert decision.proactive_level == "low"
        assert decision.memory_write_policy == "conservative"
        assert decision.tts_style == "soft"

    def test_tired_emotion_adds_gentle_hint(self):
        engine = BehaviorEngine()
        decision = engine.decide(make_context("companion", user_emotion="tired"))

        assert decision.proactive_level == "low"
        assert decision.tts_style == "gentle"
        assert any("低能量" in h for h in decision.prompt_hints)

    def test_worried_emotion_adds_gentle_hint(self):
        engine = BehaviorEngine()
        decision = engine.decide(make_context("companion", user_emotion="worried"))

        assert decision.tts_style == "gentle"
        assert any("低能量" in h for h in decision.prompt_hints)

    def test_capability_browser_automation_disabled_by_default(self):
        engine = BehaviorEngine()
        decision = engine.decide(make_context("companion"))

        caps = decision.capabilities
        assert caps["browser_automation"].enabled is False
        assert caps["browser_automation"].requires_confirmation is True

    def test_capability_mcp_disabled_by_default(self):
        engine = BehaviorEngine()
        decision = engine.decide(make_context("companion"))

        assert decision.capabilities["mcp"].enabled is False

    def test_capability_local_launcher_enabled_by_default(self):
        engine = BehaviorEngine()
        decision = engine.decide(make_context("companion"))

        assert decision.capabilities["local_launcher"].enabled is True

    def test_local_agent_settings_override_capability(self):
        engine = BehaviorEngine()
        ctx = make_context("companion", local_agent_settings={
            "browser_reader_enabled": False,
            "mcp_enabled": True,
        })
        decision = engine.decide(ctx)

        assert decision.capabilities["browser_reader"].enabled is False
        assert decision.capabilities["mcp"].enabled is True

    def test_debug_reasons_contains_mode(self):
        engine = BehaviorEngine()
        decision = engine.decide(make_context("work"))

        assert any("mode=work" in r for r in decision.debug_reasons)

    def test_unknown_mode_falls_back_to_companion(self):
        engine = BehaviorEngine()
        decision = engine.decide(make_context("nonexistent_mode"))

        # Should fall back to companion behavior
        assert decision.proactive_level == "normal"
        assert "chat" in decision.allowed_tool_groups
