"""Web search service (F15 skeleton).

Real implementation deferred. Will use a search API (Google / Bing / Brave)
to return structured search results.
"""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class WebSearchService:
    """Placeholder for web search integration."""

    def search(
        self,
        query: str,
        user_id: UUID,
        max_results: int = 5,
    ) -> list[dict]:
        """Search the web and return structured results.

        Raises NotImplementedError until the feature is built.
        """
        raise NotImplementedError("WebSearchService is not yet implemented.")
