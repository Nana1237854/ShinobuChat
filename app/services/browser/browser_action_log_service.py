"""Compatibility wrapper.

New code should import from:
    app.domains.browser.logs.browser_action_log_service
"""

from app.domains.browser.logs.browser_action_log_service import BrowserActionLogService

__all__ = ["BrowserActionLogService"]