"""CapabilityRegistry — lists all platform capabilities (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    key: str
    label: str
    description: str
    default_enabled: bool
    risk_level: str
    requires_confirmation_by_default: bool


class CapabilityRegistry:
    """Unified catalog of platform capabilities.

    Each capability has a key, human-readable label, risk level, and
    default enablement. Per-user overrides are handled by CapabilityPolicyService.
    """

    def __init__(self):
        self._items: dict[str, Capability] = {
            "local_launcher": Capability(
                key="local_launcher",
                label="Local Launcher",
                description="打开本地应用",
                default_enabled=True,
                risk_level="medium",
                requires_confirmation_by_default=False,
            ),
            "browser_reader": Capability(
                key="browser_reader",
                label="Browser Reader",
                description="搜索和读取网页",
                default_enabled=True,
                risk_level="medium",
                requires_confirmation_by_default=True,
            ),
            "browser_automation": Capability(
                key="browser_automation",
                label="Browser Automation",
                description="自动化浏览器操作",
                default_enabled=False,
                risk_level="high",
                requires_confirmation_by_default=True,
            ),
            "mcp": Capability(
                key="mcp",
                label="MCP Adapter",
                description="向外部 Agent 暴露安全工具",
                default_enabled=False,
                risk_level="high",
                requires_confirmation_by_default=False,
            ),
            "download_safety": Capability(
                key="download_safety",
                label="Download Safety",
                description="下载候选识别和风险分类",
                default_enabled=True,
                risk_level="high",
                requires_confirmation_by_default=True,
            ),
        }

    def list(self) -> list[Capability]:
        return list(self._items.values())

    def get(self, key: str) -> Capability | None:
        return self._items.get(key)
