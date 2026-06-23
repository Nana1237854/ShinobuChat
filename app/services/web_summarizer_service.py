"""Web summarizer service (F15 skeleton).

Real implementation deferred. Will use an LLM to summarize web page content.
"""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class WebSummarizerService:
    """Placeholder for LLM-based web content summarization."""

    def summarize(
        self,
        content: str,
        user_id: UUID,
        max_length: int = 500,
    ) -> str:
        """Summarize web page content using an LLM.

        Raises NotImplementedError until the feature is built.
        """
        raise NotImplementedError("WebSummarizerService is not yet implemented.")
