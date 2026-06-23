"""Download candidate extractor — extracts downloadable links from a web page."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.services.web_reader_service import WebReaderService

# File extensions commonly associated with downloads
_DOWNLOAD_EXTENSIONS = {
    ".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk", ".ipa",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
    ".bat", ".cmd", ".ps1", ".sh", ".app", ".run",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".mp3", ".wav", ".flac", ".mp4", ".avi", ".mkv",
    ".jpg", ".jpeg", ".png", ".gif", ".svg",
    ".jar", ".py", ".rb", ".pl", ".msi",
    ".iso", ".img", ".bin", ".dmg",
    ".ttf", ".otf", ".woff", ".woff2",
}

_MALICIOUS_PATTERNS = [
    re.compile(r"\.exe\.", re.IGNORECASE),
    re.compile(r"\.msi\.", re.IGNORECASE),
    re.compile(r"\.bat\.", re.IGNORECASE),
    re.compile(r"\.cmd\.", re.IGNORECASE),
    re.compile(r"\.ps1\.", re.IGNORECASE),
]


class DownloadCandidateExtractor:
    """Identify download candidates from a web page's links."""

    def extract(self, links: list[dict]) -> list[dict]:
        """Given a list of link dicts (text, href), return download candidates."""
        candidates: list[dict] = []
        seen: set[str] = set()

        for link in links:
            href = (link.get("href") or "").strip()
            if not href or href in seen:
                continue
            seen.add(href)

            parsed = urlparse(href)

            # Protocol checks — handled later by risk classifier
            path = (parsed.path or "").lower()

            # Check for double-extension pattern
            if _has_double_extension(path):
                ext = _resolve_extension(path)
                candidates.append({
                    "text": link.get("text", ""),
                    "href": href,
                    "domain": parsed.netloc or "",
                    "extension": ext,
                })
                continue

            # Check for download extension
            ext = _resolve_extension(path)
            if ext in _DOWNLOAD_EXTENSIONS:
                candidates.append({
                    "text": link.get("text", ""),
                    "href": href,
                    "domain": parsed.netloc or "",
                    "extension": ext,
                })
                continue

            # Check link text for download hints
            text = (link.get("text") or "").lower()
            if any(kw in text for kw in ["下载", "download", "setup", "install", "安装"]):
                # Mark as candidate even without recognized extension
                candidates.append({
                    "text": link.get("text", ""),
                    "href": href,
                    "domain": parsed.netloc or "",
                    "extension": ext or _guess_extension_from_path(path),
                })

        return candidates


def _resolve_extension(path: str) -> str:
    """Return the last file extension."""
    parts = path.rsplit(".", maxsplit=1)
    if len(parts) == 2:
        return f".{parts[1]}".lower()
    return ""


def _has_double_extension(path: str) -> bool:
    return any(p.search(path) for p in _MALICIOUS_PATTERNS)


def _guess_extension_from_path(path: str) -> str:
    """Fallback: guess extension from path segments."""
    for seg in reversed(path.split("/")):
        ext = _resolve_extension(seg)
        if ext:
            return ext
    return ""
