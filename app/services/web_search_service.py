"""Compatibility wrapper.

New code should import from:
    app.domains.browser.web_search_service
"""

from app.domains.browser.web_search_service import WebSearchService

__all__ = ["WebSearchService"]