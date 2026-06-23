"""Browser facade service — unified entry point for all browser operations.

Aggregates WebSearch, WebReader, WebSummarizer, BrowserAutomation,
Download, permission enforcement, and action logging.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.services.ai_client import AIClient
from app.services.browser.browser_action_log_service import BrowserActionLogService
from app.services.browser.trusted_download_source_service import TrustedDownloadSourceService
from app.services.browser_automation_service import BrowserAutomationService
from app.services.config_service import ConfigService
from app.services.download_service import DownloadService
from app.services.local_agent_settings_service import LocalAgentSettingsService
from app.services.web_reader_service import WebReaderService
from app.services.web_search_service import WebSearchService
from app.services.web_summarizer_service import WebSummarizerService


class BrowserFacadeService:
    def __init__(self, db: Session, config_service: ConfigService):
        self.db = db
        self.config_service = config_service
        self.settings = LocalAgentSettingsService(db)
        self.logs = BrowserActionLogService(db)
        self.trusted = TrustedDownloadSourceService(db)

    # ── Search ──

    def search(self, user_id: UUID, query: str, max_results: int = 5) -> dict:
        self.settings.ensure_browser_reader_enabled(user_id)

        api_key = self.config_service.get_effective_value(user_id, "google_search_api_key") or ""
        cx = self.config_service.get_effective_value(user_id, "google_search_cx") or ""

        result = WebSearchService(api_key=api_key, cx=cx).search(
            query, user_id=user_id, max_results=max_results,
        )

        self.logs.record(
            user_id=user_id,
            action_type="browser_search",
            target_url=None,
            status=result.get("status", "ok"),
            message=result.get("message", ""),
            payload_json={"query": query},
        )
        return result

    # ── Read ──

    def read(self, user_id: UUID, url: str, max_chars: int = 10000) -> dict:
        self.settings.ensure_browser_reader_enabled(user_id)

        result = WebReaderService().read(url, user_id=user_id, max_chars=max_chars)

        self.logs.record(
            user_id=user_id,
            action_type="browser_read",
            target_url=url,
            status=result.get("status", "error"),
            message=result.get("message", ""),
        )
        return result

    # ── Summarize ──

    def summarize(self, user_id: UUID, url: str, question: str = "", max_chars: int = 10000) -> dict:
        self.settings.ensure_browser_reader_enabled(user_id)

        runtime = self.config_service.resolve_runtime(user_id)
        result = WebSummarizerService(ai_client=AIClient()).summarize(
            url, user_id=user_id, question=question, max_chars=max_chars,
            runtime_config=runtime,
        )

        self.logs.record(
            user_id=user_id,
            action_type="browser_summarize",
            target_url=url,
            status=result.get("status", "error"),
            message=result.get("message", ""),
        )
        return result

    # ── Open URL ──

    def open_url(self, user_id: UUID, url: str) -> dict:
        self.settings.ensure_browser_reader_enabled(user_id)

        result = BrowserAutomationService().open_url(url, user_id=user_id)

        self.logs.record(
            user_id=user_id,
            action_type="browser_open_url",
            target_url=url,
            status=result.get("status", "error"),
            message=result.get("message", ""),
        )
        return result

    # ── Download candidates ──

    def extract_download_candidates(self, user_id: UUID, url: str) -> dict:
        self.settings.ensure_browser_reader_enabled(user_id)

        result = DownloadService(self.db).extract_candidates(url, user_id=user_id)

        self.logs.record(
            user_id=user_id,
            action_type="extract_download_candidates",
            target_url=url,
            status=result.get("status", "error"),
            message=result.get("message", ""),
        )
        return result

    # ── Classify downloads ──

    def classify_downloads(self, user_id: UUID, candidates: list[dict]) -> dict:
        self.settings.ensure_browser_reader_enabled(user_id)

        result = DownloadService(self.db).classify(candidates)

        self.logs.record(
            user_id=user_id,
            action_type="classify_downloads",
            target_url=None,
            status=result.get("status", "error"),
            message=result.get("message", ""),
            payload_json={"candidate_count": len(candidates)},
        )
        return result
