"""Compatibility wrapper.

New code should import from:
    app.domains.browser.download.download_candidate_extractor
"""

from app.domains.browser.download.download_candidate_extractor import DownloadCandidateExtractor

__all__ = ["DownloadCandidateExtractor"]