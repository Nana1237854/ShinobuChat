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
from app.core.time import local_now
from app.db.session import get_db
from app.models.browser_action_log import BrowserActionLog
from app.services.local_agent_settings_service import LocalAgentSettingsService
from app.models.trusted_download_source import TrustedDownloadSource
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
from app.services.browser_automation_service import BrowserAutomationService
from app.services.config_service import ConfigService
from app.services.download_service import DownloadService
from app.services.http_client import UrllibHttpClient
from app.services.web_reader_service import WebReaderService
from app.services.web_search_service import WebSearchService
from app.services.web_summarizer_service import WebSummarizerService

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
    LocalAgentSettingsService(db).ensure_browser_reader_enabled(user_id)
    api_key = config_service.get_effective_value(user_id, "google_search_api_key") or ""
    cx = config_service.get_effective_value(user_id, "google_search_cx") or ""

    svc = WebSearchService(api_key=api_key, cx=cx)
    result = svc.search(body.query, user_id=user_id, max_results=body.max_results)
    return BrowserSearchResponse(**result)


# ---------------------------------------------------------------------------
# F14: Read
# ---------------------------------------------------------------------------

@router.post("/read", response_model=BrowserReadResponse)
def browser_read(
    body: BrowserReadRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> BrowserReadResponse:
    LocalAgentSettingsService(db).ensure_browser_reader_enabled(user_id)
    svc = WebReaderService()
    result = svc.read(body.url, user_id=user_id, max_chars=body.max_chars)
    _log_browser_action(
        db, user_id, "browser_read", body.url,
        status=result.get("status", "error"),
        message=result.get("message", ""),
    )
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
    LocalAgentSettingsService(db).ensure_browser_reader_enabled(user_id)
    from app.services.ai_client import AIClient

    runtime = config_service.resolve_runtime(user_id)
    ai_client = AIClient()
    svc = WebSummarizerService(ai_client=ai_client)
    result = svc.summarize(
        body.url, user_id=user_id, question=body.question, max_chars=body.max_chars,
        runtime_config=runtime,
    )
    _log_browser_action(
        db, user_id, "browser_summarize", body.url,
        status=result.get("status", "error"),
        message=result.get("message", ""),
    )
    return BrowserSummarizeResponse(**result)


# ---------------------------------------------------------------------------
# F14: Open URL
# ---------------------------------------------------------------------------

@router.post("/open-url", response_model=BrowserOpenUrlResponse)
def browser_open_url(
    body: BrowserOpenUrlRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> BrowserOpenUrlResponse:
    LocalAgentSettingsService(db).ensure_browser_reader_enabled(user_id)
    svc = BrowserAutomationService()
    result = svc.open_url(body.url, user_id=user_id)
    _log_browser_action(
        db, user_id, "browser_open_url", body.url,
        status=result.get("status", "error"),
        message=result.get("message", ""),
    )
    return BrowserOpenUrlResponse(**result)


# ---------------------------------------------------------------------------
# F15: Download Candidates
# ---------------------------------------------------------------------------

@router.post("/download-candidates", response_model=ExtractDownloadCandidatesResponse)
def extract_download_candidates(
    body: ExtractDownloadCandidatesRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ExtractDownloadCandidatesResponse:
    LocalAgentSettingsService(db).ensure_browser_reader_enabled(user_id)
    svc = DownloadService(db)
    result = svc.extract_candidates(body.url, user_id=user_id)
    _log_browser_action(
        db, user_id, "extract_download_candidates", body.url,
        status=result.get("status", "error"),
        message=result.get("message", ""),
    )
    return ExtractDownloadCandidatesResponse(**result)


# ---------------------------------------------------------------------------
# F15: Classify Downloads
# ---------------------------------------------------------------------------

@router.post("/classify-downloads", response_model=ClassifyDownloadResponse)
def classify_downloads(
    body: ClassifyDownloadRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ClassifyDownloadResponse:
    LocalAgentSettingsService(db).ensure_browser_reader_enabled(user_id)
    svc = DownloadService(db)
    candidates = [c.model_dump() for c in body.candidates]
    result = svc.classify(candidates)
    _log_browser_action(
        db, user_id, "classify_downloads", "",
        status=result.get("status", "error"),
        message=result.get("message", ""),
    )
    return ClassifyDownloadResponse(**result)


# ---------------------------------------------------------------------------
# F15: Trusted Download Sources
# ---------------------------------------------------------------------------

@router.get("/sources", response_model=TrustedSourceListResponse)
def list_trusted_sources(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TrustedSourceListResponse:
    rows = (
        db.query(TrustedDownloadSource)
        .filter(
            (TrustedDownloadSource.user_id == user_id)
            | (TrustedDownloadSource.user_id.is_(None))
        )
        .order_by(TrustedDownloadSource.domain)
        .all()
    )
    return TrustedSourceListResponse(
        sources=[TrustedSourceItem.model_validate(r) for r in rows]
    )


@router.post("/sources", response_model=TrustedSourceItem)
def add_trusted_source(
    body: TrustedSourceCreateRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TrustedSourceItem:
    source = TrustedDownloadSource(
        user_id=user_id,
        domain=body.domain,
        product_key=body.product_key,
        trust_level=body.trust_level,
        source_type="user",
        note=body.note,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
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
    q = (
        db.query(BrowserActionLog)
        .filter(BrowserActionLog.user_id == user_id)
    )
    if action_type:
        q = q.filter(BrowserActionLog.action_type == action_type)
    if status:
        q = q.filter(BrowserActionLog.status == status)
    q = q.order_by(BrowserActionLog.created_at.desc()).offset(offset).limit(limit)
    rows = q.all()
    return BrowserActionLogsResponse(
        logs=[BrowserActionLogItem.model_validate(r) for r in rows]
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_browser_action(
    db: Session,
    user_id: UUID,
    action_type: str,
    target_url: str,
    status: str = "started",
    message: str | None = None,
    error_detail: str | None = None,
) -> BrowserActionLog:
    log = BrowserActionLog(
        user_id=user_id,
        action_type=action_type,
        target_url=target_url or None,
        status=status,
        message=message,
        error_detail=error_detail,
        payload_json={},
        finished_at=local_now() if status in ("ok", "error", "failed") else None,
    )
    db.add(log)
    db.commit()
    return log
