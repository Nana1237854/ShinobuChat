"""Browser facade service — unified entry point for all browser operations.

Aggregates WebSearch, WebReader, WebSummarizer, BrowserAutomation,
Download, permission enforcement, action logging, and Phase 2 ActionAudit.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.observability.action_audit_service import ActionAuditService
from app.services.ai_client import AIClient
from app.domains.browser.logs.browser_action_log_service import BrowserActionLogService
from app.domains.browser.trusted_sources.trusted_download_source_service import TrustedDownloadSourceService
from app.domains.browser.browser_automation_service import BrowserAutomationService
from app.domains.capabilities.capability_policy_service import CapabilityPolicyService
from app.services.config_service import ConfigService
from app.domains.browser.download.download_service import DownloadService
from app.domains.local_agent.local_agent_settings_service import LocalAgentSettingsService
from app.domains.browser.web_reader_service import WebReaderService
from app.domains.browser.web_search_service import WebSearchService
from app.domains.browser.web_summarizer_service import WebSummarizerService

logger = logging.getLogger(__name__)


class BrowserFacadeService:
    def __init__(self, db: Session, config_service: ConfigService):
        self.db = db
        self.config_service = config_service
        self.settings = LocalAgentSettingsService(db)
        self._capability_policy = CapabilityPolicyService(db)
        self.logs = BrowserActionLogService(db)
        self.trusted = TrustedDownloadSourceService(db)
        self._audit = ActionAuditService(db)

    # ── Search ──

    def search(self, user_id: UUID, query: str, max_results: int = 5) -> dict:
        self._capability_policy.ensure(user_id, "browser_reader")

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
        try:
            self._audit.record(
                source="browser",
                action_type="browser_search",
                user_id=user_id,
                target=query,
                status=result.get("status", "ok"),
                risk_level="low",
                policy_allowed=True,
                verified=result.get("status") == "ok",
                arguments={"query": query},
                result={"result_count": len(result.get("results", []))},
                reasons=[result.get("message", "")] if result.get("message") else [],
            )
        except Exception:
            logger.warning("Browser search audit failed", exc_info=True)
        return result

    # ── Read ──

    def read(self, user_id: UUID, url: str, max_chars: int = 10000) -> dict:
        self._capability_policy.ensure(user_id, "browser_reader")

        result = WebReaderService().read(url, user_id=user_id, max_chars=max_chars)

        self.logs.record(
            user_id=user_id,
            action_type="browser_read",
            target_url=url,
            status=result.get("status", "error"),
            message=result.get("message", ""),
        )
        try:
            self._audit.record(
                source="browser",
                action_type="browser_read",
                user_id=user_id,
                target=url,
                status=result.get("status", "ok"),
                risk_level="low" if result.get("status") == "ok" else "unknown",
                policy_allowed=True,
                verified=result.get("status") == "ok",
                arguments={"url": url, "max_chars": max_chars},
                result={
                    "title": result.get("title"),
                    "content_length": len(result.get("content", "")),
                    "link_count": len(result.get("links", [])),
                },
                reasons=[result.get("message", "")] if result.get("message") else [],
            )
        except Exception:
            logger.warning("Browser read audit failed", exc_info=True)
        return result

    # ── Summarize ──

    def summarize(self, user_id: UUID, url: str, question: str = "", max_chars: int = 10000) -> dict:
        self._capability_policy.ensure(user_id, "browser_reader")

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
        try:
            self._audit.record(
                source="browser",
                action_type="browser_summarize",
                user_id=user_id,
                target=url,
                status=result.get("status", "ok"),
                risk_level="low",
                policy_allowed=True,
                verified=result.get("status") == "ok",
                arguments={"url": url, "question": question, "max_chars": max_chars},
                result={
                    "summary_length": len(result.get("summary", "")),
                    "key_points_count": len(result.get("key_points", [])),
                },
                reasons=[result.get("message", "")] if result.get("message") else [],
            )
        except Exception:
            logger.warning("Browser summarize audit failed", exc_info=True)
        return result

    # ── Open URL ──

    def open_url(self, user_id: UUID, url: str) -> dict:
        # Plan A: open-url is gated by browser_reader_enabled.
        # "open_url" means manually opening the system default browser — not
        # Playwright-level automation.  browser_automation_enabled controls
        # higher-risk automated browser actions (future).
        self._capability_policy.ensure(user_id, "browser_reader")

        result = BrowserAutomationService().open_url(url, user_id=user_id)

        self.logs.record(
            user_id=user_id,
            action_type="browser_open_url",
            target_url=url,
            status=result.get("status", "error"),
            message=result.get("message", ""),
        )
        try:
            self._audit.record(
                source="browser",
                action_type="browser_open_url",
                user_id=user_id,
                target=url,
                status=result.get("status", "ok"),
                risk_level="low",
                policy_allowed=True,
                verified=result.get("status") == "ok",
                arguments={"url": url},
                result={"message": result.get("message")},
                reasons=[],
            )
        except Exception:
            logger.warning("Browser open_url audit failed", exc_info=True)
        return result

    # ── Download candidates ──

    def extract_download_candidates(self, user_id: UUID, url: str) -> dict:
        self._capability_policy.ensure(user_id, "browser_reader")

        result = DownloadService(self.db).extract_candidates(url, user_id=user_id)

        self.logs.record(
            user_id=user_id,
            action_type="extract_download_candidates",
            target_url=url,
            status=result.get("status", "error"),
            message=result.get("message", ""),
        )
        try:
            self._audit.record(
                source="download",
                action_type="extract_download_candidates",
                user_id=user_id,
                target=url,
                status=result.get("status", "ok"),
                risk_level="low",
                policy_allowed=True,
                verified=result.get("status") == "ok",
                arguments={"url": url},
                result={"candidate_count": len(result.get("candidates", []))},
                reasons=[],
            )
        except Exception:
            logger.warning("Download extract audit failed", exc_info=True)
        return result

    # ── Classify downloads ──

    def classify_downloads(self, user_id: UUID, candidates: list[dict]) -> dict:
        self._capability_policy.ensure(user_id, "browser_reader")

        result = DownloadService(self.db).classify(candidates)

        self.logs.record(
            user_id=user_id,
            action_type="classify_downloads",
            target_url=None,
            status=result.get("status", "error"),
            message=result.get("message", ""),
            payload_json={"candidate_count": len(candidates)},
        )
        try:
            for item in result.get("classified", []):
                self._audit.record(
                    source="download",
                    action_type="classify_download",
                    user_id=user_id,
                    target=item.get("href", ""),
                    status="blocked" if item.get("risk_level") == "blocked" else "ok",
                    risk_level=item.get("risk_level", "unknown"),
                    requires_confirmation=item.get("requires_confirmation", False),
                    policy_allowed=item.get("risk_level") != "blocked",
                    verified=True,
                    arguments={"candidate": item},
                    result={"suggested_action": item.get("suggested_action")},
                    reasons=item.get("reasons", []),
                    checked_fields={
                        "extension": item.get("extension"),
                        "domain": item.get("domain"),
                    },
                )
        except Exception:
            logger.warning("Download classify audit failed", exc_info=True)
        return result
