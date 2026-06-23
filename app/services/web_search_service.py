"""Web search service — Google Custom Search API integration."""

from __future__ import annotations

import logging
from urllib.parse import urlencode
from uuid import UUID

from app.services.http_client import HttpClientError, UrllibHttpClient

logger = logging.getLogger(__name__)

_GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


class WebSearchService:
    """Structured web search via Google Custom Search JSON API."""

    def __init__(
        self,
        http_client: UrllibHttpClient | None = None,
        api_key: str = "",
        cx: str = "",
    ) -> None:
        self._http = http_client or UrllibHttpClient()
        self._api_key = api_key
        self._cx = cx

    def configure(self, api_key: str, cx: str) -> None:
        self._api_key = api_key
        self._cx = cx

    def search(
        self,
        query: str,
        user_id: UUID | None = None,
        max_results: int = 5,
    ) -> dict:
        """Search the web and return structured results.

        Returns:
          dict with keys: status ("ok" | "error"), results (list), message
        """
        if not self._api_key or not self._cx:
            return {
                "status": "error",
                "results": [],
                "message": "Search is not configured. Please set Google Search API key and CX in settings.",
            }

        try:
            qs = urlencode({
                "key": self._api_key,
                "cx": self._cx,
                "q": query,
                "num": min(max_results, 10),
            })
            request_url = f"{_GOOGLE_CSE_URL}?{qs}"
            data = self._http.request_json(
                request_url,
                headers={"Referer": "https://shinobu.chat"},
                timeout=15,
            )
        except HttpClientError as exc:
            logger.warning("Google CSE request failed: %s", exc)
            return {
                "status": "error",
                "results": [],
                "message": f"Search request failed: {exc}",
            }

        items = data.get("items", [])
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in items
        ]
        return {"status": "ok", "results": results, "message": ""}
