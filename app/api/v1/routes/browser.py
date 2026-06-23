"""Browser reader, search, download safety, and automation routes.

F14: Browser Reader — search, read, summarize, open-url
F15: Download Safety — extract candidates, classify risks
F16: Action logs — browser action log retrieval
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_config_service, get_current_user_id
from app.db.session import get_db
from app.schemas.browser import (
    BrowserActionLogItem,
    BrowserActionLogsResponse,
    BrowserActionRequest,
    BrowserActionResponse,
    BrowserOpenUrlRequest,
    BrowserOpenUrlResponse,
    BrowserReadRequest,
    BrowserReadResponse,
    BrowserSearchRequest,
    BrowserSearchResponse,
    BrowserSummarizeRequest,
    BrowserSummarizeResponse,
    ClassifyDownloadRequest,
    ClassifyDownloadResponse,
    ExtractDownloadCandidatesRequest,
    ExtractDownloadCandidatesResponse,
    TrustedSourceCreateRequest,
    TrustedSourceItem,
    TrustedSourceListResponse,
)
from app.services.browser.browser_facade_service import BrowserFacadeService
from app.services.browser.browser_action_log_service import BrowserActionLogService
from app.services.browser.trusted_download_source_service import TrustedDownloadSourceService
from app.services.config_service import ConfigService

router = APIRouter(prefix="/browser", tags=["browser"])


# ---------------------------------------------------------------------------
# F14: Search
# ---------------------------------------------------------------------------

@router.post("/search", response_model=BrowserSearchResponse)
def browser_search(
    body: BrowserSearchRequest,
    user_id: UUID = Depends(get_current_user_id),
    config_service: ConfigService = Depends(get_config_service),
    db: Session = Depends(get_db),
) -> BrowserSearchResponse:
    result = BrowserFacadeService(db, config_service).search(user_id, body.query, body.max_results)
    return BrowserSearchResponse(**result)


# ---------------------------------------------------------------------------
# F14: Read
# ---------------------------------------------------------------------------

@router.post("/read", response_model=BrowserReadResponse)
def browser_read(
    body: BrowserReadRequest,
    user_id: UUID = Depends(get_current_user_id),
    config_service: ConfigService = Depends(get_config_service),
    db: Session = Depends(get_db),
) -> BrowserReadResponse:
    result = BrowserFacadeService(db, config_service).read(user_id, body.url, body.max_chars)
    return BrowserReadResponse(**result)


# ---------------------------------------------------------------------------
# F14: Summarize
# ---------------------------------------------------------------------------

@router.post("/summarize", response_model=BrowserSummarizeResponse)
def browser_summarize(
    body: BrowserSummarizeRequest,
    user_id: UUID = Depends(get_current_user_id),
    config_service: ConfigService = Depends(get_config_service),
    db: Session = Depends(get_db),
) -> BrowserSummarizeResponse:
    result = BrowserFacadeService(db, config_service).summarize(
        user_id, body.url, body.question, body.max_chars,
    )
    return BrowserSummarizeResponse(**result)


# ---------------------------------------------------------------------------
# F14: Open URL
# ---------------------------------------------------------------------------

@router.post("/open-url", response_model=BrowserOpenUrlResponse)
def browser_open_url(
    body: BrowserOpenUrlRequest,
    user_id: UUID = Depends(get_current_user_id),
    config_service: ConfigService = Depends(get_config_service),
    db: Session = Depends(get_db),
) -> BrowserOpenUrlResponse:
    result = BrowserFacadeService(db, config_service).open_url(user_id, body.url)
    return BrowserOpenUrlResponse(**result)


# ---------------------------------------------------------------------------
# F15: Download Candidates
# ---------------------------------------------------------------------------

@router.post("/download-candidates", response_model=ExtractDownloadCandidatesResponse)
def extract_download_candidates(
    body: ExtractDownloadCandidatesRequest,
    user_id: UUID = Depends(get_current_user_id),
    config_service: ConfigService = Depends(get_config_service),
    db: Session = Depends(get_db),
) -> ExtractDownloadCandidatesResponse:
    result = BrowserFacadeService(db, config_service).extract_download_candidates(user_id, body.url)
    return ExtractDownloadCandidatesResponse(**result)


# ---------------------------------------------------------------------------
# F15: Classify Downloads
# ---------------------------------------------------------------------------

@router.post("/classify-downloads", response_model=ClassifyDownloadResponse)
def classify_downloads(
    body: ClassifyDownloadRequest,
    user_id: UUID = Depends(get_current_user_id),
    config_service: ConfigService = Depends(get_config_service),
    db: Session = Depends(get_db),
) -> ClassifyDownloadResponse:
    candidates = [c.model_dump() for c in body.candidates]
    result = BrowserFacadeService(db, config_service).classify_downloads(user_id, candidates)
    return ClassifyDownloadResponse(**result)


# ---------------------------------------------------------------------------
# F15: Trusted Download Sources
# ---------------------------------------------------------------------------

@router.get("/sources", response_model=TrustedSourceListResponse)
def list_trusted_sources(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TrustedSourceListResponse:
    svc = TrustedDownloadSourceService(db)
    rows = svc.list_sources(user_id)
    return TrustedSourceListResponse(
        sources=[TrustedSourceItem.model_validate(r) for r in rows]
    )


@router.post("/sources", response_model=TrustedSourceItem)
def add_trusted_source(
    body: TrustedSourceCreateRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TrustedSourceItem:
    svc = TrustedDownloadSourceService(db)
    source = svc.create_source(
        user_id=user_id,
        domain=body.domain,
        product_key=body.product_key,
        trust_level=body.trust_level,
        note=body.note,
    )
    return TrustedSourceItem.model_validate(source)


# ---------------------------------------------------------------------------
# F16: Browser Action Logs
# ---------------------------------------------------------------------------

@router.get("/actions/logs", response_model=BrowserActionLogsResponse)
def get_browser_action_logs(
    user_id: UUID = Depends(get_current_user_id),
    action_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> BrowserActionLogsResponse:
    svc = BrowserActionLogService(db)
    rows = svc.list_logs(user_id, action_type=action_type, status=status, limit=limit, offset=offset)
    return BrowserActionLogsResponse(
        logs=[BrowserActionLogItem.model_validate(r) for r in rows]
    )
