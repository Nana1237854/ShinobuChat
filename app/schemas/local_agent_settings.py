"""Schemas for Local Agent permission settings (F16)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LocalAgentSettingsOut(BaseModel):
    local_launcher_enabled: bool = True
    browser_reader_enabled: bool = True
    browser_automation_enabled: bool = False
    mcp_enabled: bool = False
    allow_direct_open_music: bool = True
    allow_direct_open_browser: bool = True
    require_confirm_for_executable: bool = True
    require_confirm_for_unknown_url: bool = True


class LocalAgentSettingsPatch(BaseModel):
    local_launcher_enabled: bool | None = None
    browser_reader_enabled: bool | None = None
    browser_automation_enabled: bool | None = None
    mcp_enabled: bool | None = None
    allow_direct_open_music: bool | None = None
    allow_direct_open_browser: bool | None = None
    require_confirm_for_executable: bool | None = None
    require_confirm_for_unknown_url: bool | None = None
