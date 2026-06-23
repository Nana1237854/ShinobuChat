"""Download risk classifier — rule-based risk classification for download URLs.

Three-layer classification:
1. Hard blocklist — immediate blocked/high
2. Trusted source lookup — can lower to trusted/low
3. LLM advisory only — cannot override blocked/high
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.trusted_download_source import TrustedDownloadSource

logger = logging.getLogger(__name__)

_BLOCKED_SCHEMES = {"file", "javascript", "data", "vbscript", "about"}

_BLOCKED_HOST_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(localhost|127\.\d+\.\d+\.\d+|0\.0\.0\.0)$"),
    re.compile(r"^10\..*"),
    re.compile(r"^172\.(1[6-9]|2\d|3[01])\..*"),
    re.compile(r"^192\.168\..*"),
    re.compile(r"^169\.254\..*"),
]

_DOUBLE_EXTENSION_PATTERN = re.compile(
    r"\.(jpg|jpeg|png|gif|bmp|svg|pdf|docx?|xlsx?|pptx?|txt|"
    r"mp3|mp4|avi|mkv|mov|wav|flac|html?|css|js|json|xml|"
    r"csv|log|tmp|bak|dat)\.(exe|msi|bat|cmd|ps1|scr|vbs|com)$",
    re.IGNORECASE,
)

_HIGH_RISK_KEYWORDS = [
    "crack", "keygen", "patcher", "破解", "绿色版",
    "高速下载", "高速下载器", "安全下载器", "p2p下载器",
    "注册机", "激活工具", "hack", "cheat",
    "bypass", "injector", "trojan", "malware",
]

_HIGH_RISK_EXTENSIONS = {".exe", ".msi", ".bat", ".cmd", ".ps1", ".scr", ".vbs", ".jar"}

_MEDIUM_RISK_EXTENSIONS = {".zip", ".rar", ".7z", ".iso", ".dmg", ".run", ".sh", ".app"}


class DownloadRiskClassifier:
    """Classifies download candidates by risk level."""

    def __init__(self, db: Session | None = None) -> None:
        self._db = db

    def classify(self, candidates: list[dict]) -> list[dict]:
        """Classify each candidate and return with risk metadata.

        Args:
            candidates: list of dicts with keys text, href, domain, extension

        Returns:
            list of dicts with added keys: risk_level, reasons, suggested_action,
            requires_confirmation
        """
        trusted_domains = self._load_trusted_domains() if self._db else {}

        results: list[dict] = []
        for c in candidates:
            href = c.get("href", "")
            text = c.get("text", "")
            domain = c.get("domain", "")
            extension = c.get("extension", "")

            risk_level, reasons = self._classify_one(
                href, text, domain, extension, trusted_domains
            )

            requires_confirmation = risk_level != "blocked"
            if risk_level in ("trusted", "low") and extension in _HIGH_RISK_EXTENSIONS:
                requires_confirmation = True
                reasons.append("Trusted source but file is an executable — requires confirmation")

            suggested_action = self._suggested_action(risk_level, requires_confirmation)

            results.append({
                "text": text,
                "href": href,
                "domain": domain,
                "extension": extension,
                "risk_level": risk_level,
                "reasons": reasons,
                "suggested_action": suggested_action,
                "requires_confirmation": requires_confirmation,
            })

        return results

    def classify_one(self, candidate: dict) -> dict:
        """Classify a single candidate. Returns the enriched dict."""
        return self.classify([candidate])[0]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _classify_one(
        self,
        href: str,
        text: str,
        domain: str,
        extension: str,
        trusted_domains: dict[str, dict],
    ) -> tuple[str, list[str]]:
        """Return (risk_level, reasons) for one candidate."""

        # --- Layer 1: hard blocklist ---
        blocked_reason = self._check_blocklist(href, domain)
        if blocked_reason:
            return "blocked", [blocked_reason]

        # High risk from keywords
        high_reasons: list[str] = []
        text_lower = text.lower()
        for kw in _HIGH_RISK_KEYWORDS:
            if kw.lower() in text_lower:
                high_reasons.append(f"Contains high-risk keyword: '{kw}'")
        if _has_double_extension(href):
            high_reasons.append("Double extension disguise detected")

        # High risk from executable and not trusted
        if extension in _HIGH_RISK_EXTENSIONS and domain not in trusted_domains:
            high_reasons.append(f"Executable file extension ({extension}) from untrusted source")

        if high_reasons:
            return "high", high_reasons

        # --- Layer 2: trusted sources ---
        trust = trusted_domains.get(domain)
        if trust:
            return trust.get("trust_level", "trusted"), ["Domain is in trusted sources list"]

        # Medium risk extensions
        if extension in _MEDIUM_RISK_EXTENSIONS:
            return "medium", [f"Archive/installer file ({extension}) from unverified source"]

        # Low/unknown
        if extension in {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".mp3", ".mp4", ".png", ".jpg"}:
            return "low", ["Common file format, low risk"]
        if extension:
            return "unknown", ["Unknown file type"]

        return "unknown", ["No recognized download risk indicators"]

    def _check_blocklist(self, href: str, domain: str) -> str | None:
        """Return a block reason if the URL should be blocked outright."""
        try:
            parsed = urlparse(href)
        except Exception:
            return "Invalid URL format"

        if parsed.scheme.lower() in _BLOCKED_SCHEMES:
            return f"Blocked URL scheme: {parsed.scheme}://"

        if parsed.scheme not in {"http", "https"} and parsed.scheme:
            return f"Non-http(s) scheme: {parsed.scheme}://"

        hostname = (parsed.hostname or "").lower()
        for pat in _BLOCKED_HOST_PATTERNS:
            if pat.match(hostname):
                return f"Blocked host: {hostname}"

        if _has_double_extension(href):
            return "Blocked: double extension disguise (e.g., .jpg.exe)"

        return None

    def _suggested_action(self, risk_level: str, requires_confirmation: bool) -> str:
        if risk_level == "blocked":
            return "This link is blocked by security policy and cannot be downloaded."
        if risk_level == "high":
            return "This download is flagged as high risk. Manual review required."
        if requires_confirmation:
            return "Confirm before downloading. Do not run the installer until you trust the source."
        if risk_level == "medium":
            return "Verify the source before opening the downloaded file."
        return "Download appears safe, but always verify file contents."

    def _load_trusted_domains(self) -> dict[str, dict]:
        if self._db is None:
            return {}
        rows = self._db.query(TrustedDownloadSource).filter(
            TrustedDownloadSource.enabled.is_(True)
        ).all()
        return {
            row.domain: {"trust_level": row.trust_level, "note": row.note}
            for row in rows
        }


def _has_double_extension(href: str) -> bool:
    path = urlparse(href).path or ""
    # Check for double extension disguise (e.g., .jpg.exe, .pdf.msi)
    if _DOUBLE_EXTENSION_PATTERN.search(path):
        return True
    # Also catch patterns like .exe.jpg (reverse order)
    return bool(re.search(
        r"\.(exe|msi|bat|cmd|ps1|scr|vbs)\.(jpg|jpeg|png|gif|pdf|doc|txt|mp3|zip)$",
        path, re.IGNORECASE,
    ))
