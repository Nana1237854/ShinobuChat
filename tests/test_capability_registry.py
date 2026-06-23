"""Unit tests for CapabilityRegistry (Phase 3)."""

import pytest

from app.domains.capabilities.capability_registry import Capability, CapabilityRegistry


class TestCapabilityRegistry:
    def setup_method(self):
        self.registry = CapabilityRegistry()

    def test_list_returns_all_registered_capabilities(self):
        caps = self.registry.list()
        keys = {c.key for c in caps}
        assert "local_launcher" in keys
        assert "browser_reader" in keys
        assert "browser_automation" in keys
        assert "mcp" in keys
        assert "download_safety" in keys

    def test_get_returns_correct_capability(self):
        c = self.registry.get("browser_reader")
        assert c is not None
        assert c.key == "browser_reader"
        assert c.default_enabled is True
        assert c.risk_level == "medium"

    def test_get_unknown_returns_none(self):
        assert self.registry.get("nonexistent") is None

    def test_browser_automation_is_high_risk_disabled(self):
        c = self.registry.get("browser_automation")
        assert c.risk_level == "high"
        assert c.default_enabled is False
        assert c.requires_confirmation_by_default is True

    def test_mcp_is_high_risk_disabled(self):
        c = self.registry.get("mcp")
        assert c.risk_level == "high"
        assert c.default_enabled is False

    def test_local_launcher_is_medium_risk_enabled(self):
        c = self.registry.get("local_launcher")
        assert c.risk_level == "medium"
        assert c.default_enabled is True


class TestCapabilityDataclass:
    def test_capability_is_frozen(self):
        c = Capability(
            key="test", label="Test", description="desc",
            default_enabled=True, risk_level="low",
            requires_confirmation_by_default=False,
        )
        with pytest.raises(Exception):
            c.key = "other"  # type: ignore
