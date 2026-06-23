"""Compatibility wrapper.

New code should import from:
    app.domains.browser.download.download_service
"""

from app.domains.browser.download.download_service import DownloadService

__all__ = ["DownloadService"]