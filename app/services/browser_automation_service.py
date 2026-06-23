"""Compatibility wrapper.

New code should import from:
    app.domains.browser.browser_automation_service
"""

from app.domains.browser.browser_automation_service import BrowserAutomationService

__all__ = ["BrowserAutomationService"]