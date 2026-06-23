"""Compatibility wrapper.

New code should import from:
    app.domains.browser.web_summarizer_service
"""

from app.domains.browser.web_summarizer_service import WebSummarizerService

__all__ = ["WebSummarizerService"]