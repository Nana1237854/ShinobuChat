"""Compatibility wrapper.

New code should import from:
    app.domains.browser.trusted_sources.trusted_download_source_service
"""

from app.domains.browser.trusted_sources.trusted_download_source_service import TrustedDownloadSourceService

__all__ = ["TrustedDownloadSourceService"]