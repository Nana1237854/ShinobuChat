"""Unified ActionAuditLog service (Phase 2).

Records audit entries for tool execution, browser operations, local agent
actions, MCP calls, download classification, and task events.

Sensitive field redaction applies to arguments before persistence.
Audit write failures must never affect the main response path.
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.time import local_now as _utc_now
from app.models.action_audit_log import ActionAuditLog

logger = logging.getLogger(__name__)

SENSITIVE_KEYWORDS = {
    "api_key", "apikey", "token", "access_token", "refresh_token",
    "password", "secret", "authorization", "cookie",
}

SENSITIVE_QUERY_KEYS = {
    "token", "access_token", "refresh_token", "api_key", "apikey",
    "key", "secret", "password", "auth", "authorization", "cookie",
}


def redact_payload(payload: dict | None) -> dict:
    if not payload:
        return {}
    result: dict = {}
    for key, value in payload.items():
        lowered = key.lower()
        if any(s in lowered for s in SENSITIVE_KEYWORDS):
            result[key] = "***REDACTED***"
        elif isinstance(value, dict):
            result[key] = redact_payload(value)
        elif isinstance(value, list):
            result[key] = [
                redact_payload(v) if isinstance(v, dict)
                else _sanitize_value(v)
                for v in value
            ]
        else:
            result[key] = _sanitize_value(value)
    return result


def _redact_url(text: str | None) -> str:
    """Redact sensitive query parameters from a URL string."""
    if not text or not isinstance(text, str):
        return ""
    try:
        parsed = urlparse(text)
    except Exception:
        return text
    if not parsed.query:
        return text
    try:
        params = parse_qsl(parsed.query, keep_blank_values=True)
    except Exception:
        return text
    redacted = [
        (k, "REDACTED" if k.lower() in SENSITIVE_QUERY_KEYS else v)
        for k, v in params
    ]
    try:
        clean = urlunparse(parsed._replace(query=urlencode(redacted)))
    except Exception:
        clean = text
    return clean


def _is_url_like(value) -> bool:
    """Heuristic: treat strings starting with http:// or https:// as URLs."""
    if not isinstance(value, str):
        return False
    return value.startswith(("http://", "https://"))


def _sanitize_value(value) -> object:
    """Redact URL query params for URL-like strings, truncate others."""
    if isinstance(value, str):
        if _is_url_like(value):
            return _redact_url(value)
        return _truncate(value)
    return value


def _truncate(value, limit: int = 500) -> str:
    text = str(value)
    if len(text) > limit:
        return text[:limit] + "...[truncated]"
    return text


def summarize_result(result, limit: int = 500) -> str:
    text = " ".join(str(result or "").split())
    return text[:limit] + ("...[truncated]" if len(text) > limit else "")


class ActionAuditService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        source: str,
        action_type: str,
        user_id: UUID | None = None,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        target: str = "",
        status: str = "unknown",
        risk_level: str = "unknown",
        requires_confirmation: bool = False,
        policy_allowed: bool = True,
        verified: bool = False,
        arguments: dict | None = None,
        result=None,
        reasons: list[str] | None = None,
        checked_fields: dict | None = None,
    ):
        safe_target = _sanitize_value(target) if target else ""

        log = ActionAuditLog(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            source=source,
            action_type=action_type,
            target=str(safe_target),
            status=status,
            risk_level=risk_level,
            requires_confirmation=requires_confirmation,
            policy_allowed=policy_allowed,
            verified=verified,
            arguments_redacted=redact_payload(arguments),
            result_summary=summarize_result(result),
            reasons=reasons or [],
            checked_fields=checked_fields or {},
            finished_at=_utc_now() if status in {"ok", "error", "failed", "blocked"} else None,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_for_user(self, user_id: UUID, source: str | None = None, limit: int = 50, offset: int = 0):
        q = self.db.query(ActionAuditLog).filter(ActionAuditLog.user_id == user_id)
        if source:
            q = q.filter(ActionAuditLog.source == source)
        return (
            q.order_by(ActionAuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_for_conversation(self, user_id: UUID, conversation_id: UUID, limit: int = 50):
        return (
            self.db.query(ActionAuditLog)
            .filter(
                ActionAuditLog.user_id == user_id,
                ActionAuditLog.conversation_id == conversation_id,
            )
            .order_by(ActionAuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def list_for_message(self, user_id: UUID, message_id: UUID):
        return (
            self.db.query(ActionAuditLog)
            .filter(
                ActionAuditLog.user_id == user_id,
                ActionAuditLog.message_id == message_id,
            )
            .order_by(ActionAuditLog.created_at.desc())
            .all()
        )

    def get(self, audit_id: UUID, user_id: UUID):
        return (
            self.db.query(ActionAuditLog)
            .filter(ActionAuditLog.id == audit_id, ActionAuditLog.user_id == user_id)
            .first()
        )


