"""Download service — orchestrates download candidate extraction and risk classification."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.browser.download.download_candidate_extractor import DownloadCandidateExtractor
from app.domains.browser.download.download_risk_classifier import DownloadRiskClassifier
from app.domains.browser.web_reader_service import WebReaderService

logger = logging.getLogger(__name__)


class DownloadService:
    """High-level service for download discovery and safety classification."""

    def __init__(self, db: Session | None = None) -> None:
        self._extractor = DownloadCandidateExtractor()
        self._classifier = DownloadRiskClassifier(db)

    def extract_candidates(self, url: str, user_id: UUID | None = None) -> dict:
        """Read a page and extract download candidates.

        Returns:
          dict with status, candidates (list), message
        """
        reader = WebReaderService()
        result = reader.read(url, user_id=user_id)
        if result["status"] != "ok":
            return {
                "status": "error",
                "candidates": [],
                "message": result.get("message", "Failed to read page."),
            }

        candidates = self._extractor.extract(result.get("links", []))
        return {
            "status": "ok",
            "candidates": candidates,
            "message": f"Found {len(candidates)} download candidate(s).",
        }

    def classify(self, candidates: list[dict]) -> dict:
        """Classify a list of download candidates by risk.

        Returns:
          dict with status, classified (list), message
        """
        classified = self._classifier.classify(candidates)
        high_count = sum(1 for c in classified if c["risk_level"] == "high")
        blocked_count = sum(1 for c in classified if c["risk_level"] == "blocked")
        return {
            "status": "ok",
            "classified": classified,
            "message": (
                f"Classified {len(classified)} item(s). "
                f"High risk: {high_count}, Blocked: {blocked_count}."
            ),
        }
