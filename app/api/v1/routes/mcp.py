"""MCP status and settings API (F14.5).

Frontend-facing endpoints for MCP status checks and configuration.
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.mcp.config import MCP_ENABLED, MCP_SAFE_TOOLS, MCP_BLOCKED_TOOLS
from app.models.user_config import UserConfig

router = APIRouter(prefix="/mcp", tags=["mcp"])

_SETTINGS_KEY = "local_agent_settings"


class McpStatusResponse(BaseModel):
    enabled: bool
    available: bool  # True when MCP server module is importable
    safe_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    default_user_configured: bool = False
    message: str = ""


class McpSettingsPatch(BaseModel):
    enabled: bool | None = None


@router.get("/status", response_model=McpStatusResponse)
def get_mcp_status(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> McpStatusResponse:
    # Check user-level override
    row = (
        db.query(UserConfig)
        .filter(UserConfig.user_id == user_id, UserConfig.field_name == _SETTINGS_KEY)
        .first()
    )
    user_mcp_enabled = MCP_ENABLED
    if row is not None:
        try:
            data = json.loads(row.field_value)
            user_mcp_enabled = data.get("mcp_enabled", MCP_ENABLED)
        except (json.JSONDecodeError, TypeError):
            pass

    from app.mcp.config import MCP_DEFAULT_USER_ID

    available = True  # Module is importable
    default_configured = bool(MCP_DEFAULT_USER_ID and MCP_DEFAULT_USER_ID.strip())
    return McpStatusResponse(
        enabled=user_mcp_enabled,
        available=available,
        safe_tools=sorted(MCP_SAFE_TOOLS),
        blocked_tools=sorted(MCP_BLOCKED_TOOLS),
        default_user_configured=default_configured,
        message=(
            "MCP Adapter is available. Default closed. "
            "Only low-risk tools are exposed to external agents."
        ),
    )


@router.patch("/settings", response_model=McpStatusResponse)
def patch_mcp_settings(
    patch: McpSettingsPatch,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> McpStatusResponse:
    if patch.enabled is not None:
        row = (
            db.query(UserConfig)
            .filter(UserConfig.user_id == user_id, UserConfig.field_name == _SETTINGS_KEY)
            .first()
        )
        if row is not None:
            try:
                data = json.loads(row.field_value)
            except (json.JSONDecodeError, TypeError):
                data = {}
        else:
            data = {}
        data["mcp_enabled"] = patch.enabled
        serialized = json.dumps(data, ensure_ascii=False)
        if row is None:
            row = UserConfig(
                user_id=user_id,
                field_name=_SETTINGS_KEY,
                field_value=serialized,
                encrypted=False,
            )
        else:
            row.field_value = serialized
        db.add(row)
        db.commit()

    return get_mcp_status(user_id=user_id, db=db)
