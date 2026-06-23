"""Web reader service (F15 skeleton).

Real implementation deferred. Will use Playwright or a headless browser
to fetch and extract readable content from web pages.
"""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class WebReaderService:
    """Placeholder for browser-based web page reading."""

    def read(
        self,
        url: str,
        user_id: UUID,
        max_chars: int = 10000,
    ) -> dict:
        """Fetch a URL and return extracted text content.

        Raises NotImplementedError until the feature is built.
        """
        raise NotImplementedError("WebReaderService is not yet implemented.")
