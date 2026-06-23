"""Compatibility wrapper.

New code should import from:
    app.domains.observability.prompt_trace_service
"""

from app.domains.observability.prompt_trace_service import PromptTraceService

__all__ = ["PromptTraceService"]