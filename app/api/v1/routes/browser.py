"""Browser automation routes (F15 skeleton).

All routes return {"status": "not_implemented"}.
Real Playwright-based automation is deferred.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user_id
from app.schemas.browser import (
    BrowserActionRequest,
    BrowserActionResponse,
    BrowserReadRequest,
    BrowserReadResponse,
)

router = APIRouter(prefix="/browser", tags=["browser"])


@router.post("/read", response_model=BrowserReadResponse)
def browser_read(
    body: BrowserReadRequest,
    user_id: UUID = Depends(get_current_user_id),
) -> BrowserReadResponse:
    return BrowserReadResponse(
        status="not_implemented",
        message="Browser Reader is not yet implemented.",
    )


@router.post("/action", response_model=BrowserActionResponse)
def browser_action(
    body: BrowserActionRequest,
    user_id: UUID = Depends(get_current_user_id),
) -> BrowserActionResponse:
    return BrowserActionResponse(
        status="not_implemented",
        message="Browser Automation is not yet implemented.",
    )


@router.post("/download", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def browser_download(
    user_id: UUID = Depends(get_current_user_id),
) -> dict:
    return {"status": "not_implemented", "message": "Browser Download is not yet implemented."}


@router.get("/sources", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def browser_sources(
    user_id: UUID = Depends(get_current_user_id),
) -> dict:
    return {"status": "not_implemented", "message": "Browser Trusted Sources is not yet implemented."}
