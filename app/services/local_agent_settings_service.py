"""Local Agent settings service (F16).

Reads per-user permission toggles from the user_configs table and provides
enforcement helpers that raise ``PermissionDeniedError`` when a capability
is disabled.

Usage in routes / services / tools::

    settings_svc = LocalAgentSettingsService(db)
    settings_svc.ensure_local_launcher_enabled(user_id)
    settings_svc.ensure_browser_reader_enabled(user_id)
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.models.user_config import UserConfig

logger = logging.getLogger(__name__)

_SETTINGS_KEY = "local_agent_settings"

_DEFAULTS = {
    "local_launcher_enabled": True,
    "browser_reader_enabled": True,
    "browser_automation_enabled": False,
    "mcp_enabled": False,
    "allow_direct_open_music": True,
    "allow_direct_open_browser": True,
    "require_confirm_for_executable": True,
    "require_confirm_for_unknown_url": True,
}


class LocalAgentSettingsService:
    """Read and enforce local-agent permission toggles."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_settings(self, user_id: UUID) -> dict:
        """Return the full settings dict (defaults merged with saved values)."""
        row = (
            self._db.query(UserConfig)
            .filter(UserConfig.user_id == user_id, UserConfig.field_name == _SETTINGS_KEY)
            .first()
        )
        if row is None:
            return dict(_DEFAULTS)
        try:
            saved = json.loads(row.field_value)
        except (json.JSONDecodeError, TypeError):
            return dict(_DEFAULTS)
        merged = dict(_DEFAULTS)
        merged.update({k: v for k, v in saved.items() if k in _DEFAULTS})
        return merged

    # -- enforcement helpers --

    def ensure_local_launcher_enabled(self, user_id: UUID) -> None:
        if not self.get_settings(user_id).get("local_launcher_enabled", True):
            raise ForbiddenError(
                "Local Launcher 已关闭。请在设置 → 权限中心中开启后再试。"
            )

    def ensure_browser_reader_enabled(self, user_id: UUID) -> None:
        if not self.get_settings(user_id).get("browser_reader_enabled", True):
            raise ForbiddenError(
                "Browser Reader 已关闭。请在设置 → 权限中心中开启后再试。"
            )

    def ensure_browser_automation_enabled(self, user_id: UUID) -> None:
        if not self.get_settings(user_id).get("browser_automation_enabled", False):
            raise ForbiddenError(
                "Browser Automation 默认关闭。请在设置 → 权限中心中开启后再试。"
            )

    def ensure_mcp_enabled(self, user_id: UUID) -> None:
        if not self.get_settings(user_id).get("mcp_enabled", False):
            raise ForbiddenError(
                "MCP 集成默认关闭。请在设置 → 权限中心中开启后再试。"
            )

    def save_settings(self, user_id: UUID, patch: dict) -> dict:
        """Merge *patch* into current settings and persist. Returns merged dict."""
        current = self.get_settings(user_id)
        for key, value in patch.items():
            if key in _DEFAULTS and value is not None:
                current[key] = value

        serialized = json.dumps(current, ensure_ascii=False)

        row = (
            self._db.query(UserConfig)
            .filter(UserConfig.user_id == user_id, UserConfig.field_name == _SETTINGS_KEY)
            .first()
        )

        if row is None:
            row = UserConfig(
                user_id=user_id,
                field_name=_SETTINGS_KEY,
                field_value=serialized,
                encrypted=False,
            )
        else:
            row.field_value = serialized

        self._db.add(row)
        self._db.commit()
        return current

    def is_local_launcher_enabled(self, user_id: UUID) -> bool:
        return self.get_settings(user_id).get("local_launcher_enabled", True)

    def is_browser_reader_enabled(self, user_id: UUID) -> bool:
        return self.get_settings(user_id).get("browser_reader_enabled", True)
