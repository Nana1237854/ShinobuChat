"""Compatibility wrapper.

New code should import from:
    app.domains.browser.download.download_risk_classifier
"""

from app.domains.browser.download.download_risk_classifier import DownloadRiskClassifier, DownloadRiskDecision

__all__ = ["DownloadRiskClassifier", "DownloadRiskDecision"]