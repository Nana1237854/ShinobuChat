"""MCP status and settings API (F14.5).

Frontend-facing endpoints for MCP status checks and configuration.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.mcp.config import MCP_ENABLED, MCP_SAFE_TOOLS, MCP_BLOCKED_TOOLS, MCP_DEFAULT_USER_ID
from app.services.local_agent_settings_service import LocalAgentSettingsService

router = APIRouter(prefix="/mcp", tags=["mcp"])


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
    settings = LocalAgentSettingsService(db).get_settings(user_id)
    user_mcp_enabled = settings.get("mcp_enabled", MCP_ENABLED)

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
        LocalAgentSettingsService(db).save_settings(
            user_id, {"mcp_enabled": patch.enabled}
        )

    return get_mcp_status(user_id=user_id, db=db)
