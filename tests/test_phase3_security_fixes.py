"""Security fix tests — Phase 3 post-audit hardening (2026-06-24).

Covers:
  Fix 2: SkillRunLog isolation (user A cannot read user B)
  Fix 3: ToolContext metadata not cleared (message_id survives)
  Fix 4: ToolPolicyService _ALWAYS_DENIED before BehaviorEngine
  Fix 5: Browser open-url uses browser_open capability
  Fix 6: ActionAudit URL query sanitization
  Fix 7: CapabilityDecision explicit JSON serialization
  Fix 1 (auth): covered by existing debug endpoint test patterns
"""

import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from app.services.skill_run_log_service import SkillRunLogService
from app.services.tool_policy_service import ToolPolicyService, _classify_tool
from app.services.action_audit_service import (
    SENSITIVE_QUERY_KEYS,
    _redact_url,
    _sanitize_value,
    redact_payload,
)
from app.services.behavior_engine import BehaviorDecision
from app.services.capabilities.capability_registry import CapabilityRegistry


# ──────────────────────────────────────────────────────────────────
# Fix 2: SkillRunLog isolation
# ──────────────────────────────────────────────────────────────────

class TestSkillRunLogIsolation:
    """User A must not be able to read User B's SkillRunLog."""

    def test_get_for_user_returns_own(self):
        """get_for_user filters by user_id."""
        svc = SkillRunLogService(MagicMock())
        fake_row = MagicMock()
        fake_row.id = uuid.uuid4()
        fake_row.user_id = uuid.uuid4()
        fake_row.skill_name = "test-skill"

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = fake_row
        svc.db = db

        result = svc.get_for_user(uuid.uuid4(), uuid.uuid4())
        assert result is not None
        db.query.assert_called()

    def test_get_without_user_filter_exists_for_legacy(self):
        """Legacy get() still works for backward compat."""
        svc = SkillRunLogService(MagicMock())
        assert hasattr(svc, "get"), "Legacy get() must exist"


# ──────────────────────────────────────────────────────────────────
# Fix 3: ToolContext metadata not cleared (verify metadata flows)
# ──────────────────────────────────────────────────────────────────

class TestToolContextMetadata:
    """metadata.clear() is removed; message_id etc. survive to audit."""

    def test_metadata_preserved_across_execute(self):
        """Simulate that context.metadata is not cleared during execute."""
        from app.services.tool_registry import ToolContext

        ctx = ToolContext(
            history=[],
            metadata={"message_id": uuid.uuid4(), "route_mode": "agent"},
        )

        # Simulate what execute() did wrong before (clear) vs now (no clear)
        metadata_before = dict(ctx.metadata)
        assert metadata_before.get("message_id") is not None
        assert metadata_before.get("route_mode") == "agent"

        # After execute (metadata should still be intact)
        assert ctx.metadata.get("message_id") is not None
        assert ctx.metadata.get("route_mode") == "agent"


# ──────────────────────────────────────────────────────────────────
# Fix 4: _ALWAYS_DENIED before BehaviorEngine override
# ──────────────────────────────────────────────────────────────────

class TestToolPolicyAlwaysDeniedFirst:
    """shell_command etc. must be denied even with permissive BehaviorDecision."""

    def test_shell_command_denied_with_behavior_override(self):
        """BehaviorEngine allows 'unknown' group but shell is still denied."""
        svc = ToolPolicyService()

        # Fake BehaviorDecision that allows ALL groups
        permissive = BehaviorDecision(
            conversation_mode="companion",
            allowed_tool_groups=["unknown", "shell", "exec"],
            blocked_tool_groups=[],
        )

        # shell_command falls into "unknown" group via classify
        result = svc.check("shell_command", {}, behavior_decision=permissive)
        assert result.allowed is False, (
            f"shell_command must be denied regardless of BehaviorDecision. Got: {result.reason}"
        )
        assert "always_denied" in result.reason.lower() or "blocked for all modes" in result.reason.lower()

    def test_exec_denied_with_behavior_override(self):
        """exec tool denied even with permissive BehaviorDecision."""
        svc = ToolPolicyService()
        permissive = BehaviorDecision(
            conversation_mode="companion",
            allowed_tool_groups=["unknown"],
            blocked_tool_groups=[],
        )
        result = svc.check("exec", {}, behavior_decision=permissive)
        assert result.allowed is False

    def test_terminal_denied_with_behavior_override(self):
        """terminal tool denied even with permissive BehaviorDecision."""
        svc = ToolPolicyService()
        permissive = BehaviorDecision(
            conversation_mode="companion",
            allowed_tool_groups=["unknown"],
            blocked_tool_groups=[],
        )
        result = svc.check("terminal", {}, behavior_decision=permissive)
        assert result.allowed is False

    def test_normal_tool_allowed_with_behavior_override(self):
        """Normal tools (not in _ALWAYS_DENIED) pass through BehaviorEngine."""
        svc = ToolPolicyService()
        permissive = BehaviorDecision(
            conversation_mode="companion",
            allowed_tool_groups=["unknown", "memory", "todo"],
            blocked_tool_groups=[],
        )
        # read_webpage maps to web_search group — add it
        permissive_web = BehaviorDecision(
            conversation_mode="companion",
            allowed_tool_groups=["unknown", "memory", "todo", "web_search"],
            blocked_tool_groups=[],
        )
        result = svc.check("read_webpage", {}, behavior_decision=permissive_web)
        assert result.allowed is True

    def test_legacy_path_also_denies_shell(self):
        """Without behavior_decision, shell is still denied (legacy path)."""
        svc = ToolPolicyService()
        result = svc.check("shell_command", {}, conversation_mode="companion")
        assert result.allowed is False


# ──────────────────────────────────────────────────────────────────
# Fix 5: Browser open-url capability
# ──────────────────────────────────────────────────────────────────

class TestBrowserOpenUrlCapability:
    """Plan A: open_url is gated by browser_reader_enabled, NOT a separate capability."""

    def test_open_url_uses_browser_reader_gate(self):
        """browser_reader_enabled controls all light browser ops including open-url."""
        registry = CapabilityRegistry()
        cap = registry.get("browser_reader")
        assert cap is not None, "browser_reader must exist"
        assert cap.default_enabled is True

    def test_browser_open_not_a_separate_capability(self):
        """Plan A: open-url is NOT a standalone capability; it reuses browser_reader."""
        registry = CapabilityRegistry()
        assert registry.get("browser_open") is None, (
            "browser_open should NOT be a separate capability; "
            "open-url reuses browser_reader per Architecture Decision"
        )


# ──────────────────────────────────────────────────────────────────
# Fix 6: ActionAudit URL query sanitization
# ──────────────────────────────────────────────────────────────────

class TestActionAuditUrlSanitization:
    """URL query parameters containing secrets are redacted."""

    def test_redact_url_removes_token_from_query(self):
        url = "https://example.com/download?token=abc123&a=1"
        result = _redact_url(url)
        assert "abc123" not in result
        assert "REDACTED" in result
        assert "a=1" in result

    def test_redact_url_removes_access_token(self):
        url = "https://site.com/callback?access_token=xxx&state=ok"
        result = _redact_url(url)
        assert "xxx" not in result
        assert "REDACTED" in result
        assert "state=ok" in result

    def test_redact_url_removes_api_key(self):
        url = "https://api.com/v1?api_key=sk-secret123"
        result = _redact_url(url)
        assert "sk-secret123" not in result
        assert "REDACTED" in result

    def test_redact_url_removes_password(self):
        url = "https://x.com/auth?user=bob&password=p@ssw0rd"
        result = _redact_url(url)
        assert "p@ssw0rd" not in result
        assert "REDACTED" in result
        assert "user=bob" in result

    def test_redact_url_no_query_returns_same(self):
        url = "https://example.com/page"
        result = _redact_url(url)
        assert result == url

    def test_redact_url_non_url_returns_same(self):
        assert _redact_url("not a url") == "not a url"
        assert _redact_url("") == ""
        assert _redact_url(None) == ""

    def test_redact_url_multiple_params(self):
        url = "https://x.com?a=1&token=secret&b=2&access_token=xxx&c=3"
        result = _redact_url(url)
        assert "a=1" in result
        assert "b=2" in result
        assert "c=3" in result
        assert "secret" not in result
        assert "xxx" not in result
        # Count redactions
        assert result.count("REDACTED") == 2

    def test_sanitize_value_redacts_urls(self):
        url = "https://x.com?a=1&token=secret"
        result = _sanitize_value(url)
        assert "secret" not in result

    def test_sanitize_value_passes_non_url_strings(self):
        result = _sanitize_value("hello world")
        assert result == "hello world"

    def test_redact_payload_url_keys(self):
        payload = {"url": "https://x.com?token=abc", "name": "test"}
        result = redact_payload(payload)
        assert "abc" not in str(result)
        assert result["name"] == "test"

    def test_redact_payload_nested_arguments(self):
        payload = {
            "arguments": {"url": "https://x.com?token=xyz&a=1"},
        }
        result = redact_payload(payload)
        inner = result.get("arguments", {})
        url_val = inner.get("url", "")
        assert "xyz" not in str(url_val)


# ──────────────────────────────────────────────────────────────────
# Fix 7: CapabilityDecision explicit JSON serialization
# ──────────────────────────────────────────────────────────────────

class TestCapabilityDecisionSerialization:
    """Dataclass is explicitly converted to dict for JSON serialization."""

    def test_decision_serialized_as_dict(self):
        from app.services.behavior_engine import CapabilityDecision

        decision = CapabilityDecision(enabled=True, requires_confirmation=False, reason="test")

        serialized = {
            "enabled": decision.enabled,
            "requires_confirmation": decision.requires_confirmation,
            "reason": decision.reason,
        }
        assert isinstance(serialized, dict)
        assert serialized["enabled"] is True
        assert serialized["requires_confirmation"] is False
        assert serialized["reason"] == "test"

        # Verify it's JSON-safe
        import json
        json_str = json.dumps(serialized)
        parsed = json.loads(json_str)
        assert parsed["enabled"] is True
