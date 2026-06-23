"""Download risk classifier — rule-based risk classification for download URLs.

Three-layer classification (Phase 2 strengthened):
1. Hard blocklist — immediate blocked/high, CANNOT be overridden by trusted source
2. Trusted source lookup — can lower to trusted/low (but never override hard block)
3. LLM advisory only — cannot override blocked/high
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
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


@dataclass(frozen=True)
class DownloadRiskDecision:
    """Formalized risk decision that CANNOT be overridden by trusted source."""
    risk_level: str  # blocked / high / medium / low / trusted / unknown
    reasons: list[str]
    suggested_action: str = ""
    requires_confirmation: bool = False
    policy_allowed: bool = True
    hard_blocked: bool = False


class DownloadRiskClassifier:
    """Classifies download candidates by risk level."""

    def __init__(self, db: Session | None = None) -> None:
        self._db = db

    def classify(self, candidates: list[dict]) -> list[dict]:
        """Classify each candidate and return with risk metadata."""
        trusted_domains = self._load_trusted_domains() if self._db else {}

        results: list[dict] = []
        for c in candidates:
            href = c.get("href", "")
            text = c.get("text", "")
            domain = c.get("domain", "")
            extension = c.get("extension", "")

            decision = self._decide(href, text, domain, extension, trusted_domains)
            results.append({
                "text": text,
                "href": href,
                "domain": domain,
                "extension": extension,
                "risk_level": decision.risk_level,
                "reasons": decision.reasons,
                "suggested_action": decision.suggested_action,
                "requires_confirmation": decision.requires_confirmation,
                "policy_allowed": decision.policy_allowed,
                "hard_blocked": decision.hard_blocked,
            })

        return results

    def classify_one(self, candidate: dict) -> dict:
        """Classify a single candidate. Returns the enriched dict."""
        return self.classify([candidate])[0]

    # ------------------------------------------------------------------
    # Decision engine
    # ------------------------------------------------------------------

    def _decide(
        self,
        href: str,
        text: str,
        domain: str,
        extension: str,
        trusted_domains: dict[str, dict],
    ) -> DownloadRiskDecision:
        """Return a formal DownloadRiskDecision for one candidate.

        Hard blocklist ALWAYS wins — trusted source cannot override it.
        """
        # ── Layer 1: hard blocklist (CANNOT be overridden) ──
        blocked_reason = self._check_blocklist(href, domain)
        if blocked_reason:
            return DownloadRiskDecision(
                risk_level="blocked",
                reasons=[blocked_reason],
                suggested_action="This link is blocked by security policy and cannot be downloaded.",
                requires_confirmation=False,
                policy_allowed=False,
                hard_blocked=True,
            )

        # High risk from keywords or double-extension disguise
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
            return DownloadRiskDecision(
                risk_level="high",
                reasons=high_reasons,
                suggested_action="This download is flagged as high risk. Manual review required.",
                requires_confirmation=True,
                policy_allowed=False,
            )

        # ── Layer 2: trusted sources (only reaches here if NOT hard-blocked) ──
        trust = trusted_domains.get(domain)
        if trust:
            trust_level = trust.get("trust_level", "trusted")
            # Trusted source with executable — still requires confirmation
            confirmed = extension not in _HIGH_RISK_EXTENSIONS
            return DownloadRiskDecision(
                risk_level=trust_level,
                reasons=["Domain is in trusted sources list"],
                suggested_action=(
                    "Download appears safe, but always verify file contents."
                    if confirmed
                    else "Trusted source but file is an executable — requires confirmation"
                ),
                requires_confirmation=not confirmed,
                policy_allowed=True,
            )

        # Medium risk extensions
        if extension in _MEDIUM_RISK_EXTENSIONS:
            return DownloadRiskDecision(
                risk_level="medium",
                reasons=[f"Archive/installer file ({extension}) from unverified source"],
                suggested_action="Verify the source before opening the downloaded file.",
                requires_confirmation=True,
                policy_allowed=True,
            )

        # Low/unknown
        if extension in {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".mp3", ".mp4", ".png", ".jpg"}:
            return DownloadRiskDecision(
                risk_level="low",
                reasons=["Common file format, low risk"],
                suggested_action="Download appears safe, but always verify file contents.",
                requires_confirmation=False,
                policy_allowed=True,
            )

        if extension:
            return DownloadRiskDecision(
                risk_level="unknown",
                reasons=["Unknown file type"],
                suggested_action="Verify the source before downloading.",
                requires_confirmation=True,
                policy_allowed=True,
            )

        return DownloadRiskDecision(
            risk_level="unknown",
            reasons=["No recognized download risk indicators"],
            suggested_action="Download appears safe, but always verify file contents.",
            requires_confirmation=False,
            policy_allowed=True,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_blocklist(self, href: str, domain: str) -> str | None:
        """Return a block reason if the URL should be blocked outright.

        Hard blocklist takes priority over everything — trusted source,
        LLM advisory, etc. cannot override it.
        """
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
    if _DOUBLE_EXTENSION_PATTERN.search(path):
        return True
    return bool(re.search(
        r"\.(exe|msi|bat|cmd|ps1|scr|vbs)\.(jpg|jpeg|png|gif|pdf|doc|txt|mp3|zip)$",
        path, re.IGNORECASE,
    ))
