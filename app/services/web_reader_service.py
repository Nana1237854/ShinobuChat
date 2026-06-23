"""Compatibility wrapper.

New code should import from:
    app.domains.browser.web_reader_service
"""

from app.domains.browser.web_reader_service import WebReaderService

__all__ = ["WebReaderService"]