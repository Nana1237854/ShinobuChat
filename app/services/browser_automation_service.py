"""Browser automation service (F15 skeleton).

First version only implements browser_open(url) and browser_snapshot(url).
No automatic clicking, no downloading, no installer execution.
"""

from __future__ import annotations

import logging
import os
import subprocess
from uuid import UUID

from app.core.url_validation import validate_url_safe
from app.core.exceptions import BadRequestError

logger = logging.getLogger(__name__)


class BrowserAutomationService:
    """Controlled browser actions. Only allowlisting-safe operations."""

    def open_url(self, url: str, user_id: UUID | None = None) -> dict:
        """Open a URL in the system default browser.

        Validates URL safety first. Does not support Playwright-based
        automation in this version.
        """
        try:
            validate_url_safe(url)
        except BadRequestError as exc:
            return {
                "status": "error",
                "message": f"URL rejected by security policy: {exc}",
            }

        try:
            if os.name == "nt":
                os.startfile(url)
            else:
                subprocess.Popen(["xdg-open", url])
        except Exception as exc:
            return {
                "status": "error",
                "message": f"Failed to open URL: {exc}",
            }

        return {
            "status": "ok",
            "message": f"Opened {url} in default browser.",
        }

    def snapshot(self, url: str, user_id: UUID | None = None) -> dict:
        """Take a screenshot of a web page. Deferred to future release."""
        return {
            "status": "not_implemented",
            "message": "Browser snapshot is not yet implemented.",
        }
