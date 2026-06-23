"""Compatibility wrapper.

New code should import from:
    app.domains.browser.*
"""

from app.domains.browser.logs.browser_action_log_service import BrowserActionLogService
from app.domains.browser.trusted_sources.trusted_download_source_service import TrustedDownloadSourceService
from app.domains.browser.browser_facade_service import BrowserFacadeService

__all__ = [
    "BrowserActionLogService",
    "TrustedDownloadSourceService",
    "BrowserFacadeService",
]
