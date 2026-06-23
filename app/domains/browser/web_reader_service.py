"""Web reader service — fetch and extract readable content from web pages.

Uses BeautifulSoup for HTML parsing with SSRF protection via the existing
URL validation layer.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from uuid import UUID

from bs4 import BeautifulSoup

from app.core.exceptions import BadRequestError
from app.core.url_validation import validate_url_safe
from app.services.http_client import HttpClientError, UrllibHttpClient

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = "ShinobuChat/1.0 WebReader"


class WebReaderService:
    """Fetch and extract text, title, links, and metadata from a web page."""

    def __init__(self, http_client: UrllibHttpClient | None = None) -> None:
        self._http = http_client or UrllibHttpClient()

    def read(
        self,
        url: str,
        user_id: UUID | None = None,
        max_chars: int = 10000,
    ) -> dict:
        """Fetch a URL and return structured content.

        Returns:
          dict with keys: title, url, content, links, metadata, status
        """
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return {
                "status": "error",
                "title": "",
                "url": url,
                "content": "",
                "links": [],
                "metadata": {},
                "message": "Only http(s) URLs are supported.",
            }

        try:
            validate_url_safe(url)
        except BadRequestError as exc:
            return {
                "status": "error",
                "title": "",
                "url": url,
                "content": "",
                "links": [],
                "metadata": {},
                "message": f"URL rejected by security policy: {exc}",
            }

        try:
            response = self._http.request_bytes(
                url,
                headers={"User-Agent": _DEFAULT_USER_AGENT},
                timeout=30,
                max_download_bytes=5_000_000,
                allow_internal_ips=False,
            )
        except HttpClientError as exc:
            return {
                "status": "error",
                "title": "",
                "url": url,
                "content": "",
                "links": [],
                "metadata": {},
                "message": f"Fetch failed: {exc}",
            }

        html = response.body.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        title = _extract_title(soup)
        content = _extract_text(soup)[:max_chars]
        links = _extract_links(soup, url)

        return {
            "status": "ok",
            "title": title,
            "url": url,
            "content": content,
            "links": links,
            "metadata": {
                "content_type": response.media_type or "",
                "content_length": len(response.body),
            },
            "message": "",
        }


# ---------------------------------------------------------------------------
# HTML extraction helpers
# ---------------------------------------------------------------------------

def _extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    return ""


def _extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    body = soup.body if soup.body else soup
    return body.get_text(separator="\n", strip=True)


def _extract_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    links: list[dict] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue
        full = urljoin(base_url, href)
        if full in seen:
            continue
        seen.add(full)
        links.append({
            "text": a.get_text(strip=True) or href,
            "href": full,
        })
    return links
