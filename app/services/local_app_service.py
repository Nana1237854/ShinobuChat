"""Local application launch service (F11).

The single ``open_app()`` method is called from TWO paths:
1. Quick-intent (direct call from MessageService / AgentCoordinator)
2. Agent tool loop (via ToolRegistry → open_local_app tool → this service)

Both paths share the same implementation — no duplicated subprocess logic.
"""

from __future__ import annotations

import logging
import os
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.time import local_now
from app.models.local_action_log import LocalActionLog
from app.models.pending_action import PendingAction
from app.models.user_local_app import UserLocalApp

logger = logging.getLogger(__name__)

_SCRIPT_EXTENSIONS = {".bat", ".cmd", ".ps1"}


class LocalAppService:
    """Manage and launch user-configured local applications."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list_apps(self, user_id: uuid.UUID) -> list[UserLocalApp]:
        return (
            self.db.query(UserLocalApp)
            .filter(UserLocalApp.user_id == user_id)
            .order_by(UserLocalApp.display_name)
            .all()
        )

    def get_app(self, app_id: uuid.UUID, user_id: uuid.UUID) -> UserLocalApp:
        app = (
            self.db.query(UserLocalApp)
            .filter(UserLocalApp.id == app_id, UserLocalApp.user_id == user_id)
            .first()
        )
        if app is None:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Local app not found")
        return app

    def create_app(self, user_id: uuid.UUID, **fields: Any) -> UserLocalApp:
        # Enforce unique (user_id, app_key)
        app_key = fields.get("app_key", "")
        existing = (
            self.db.query(UserLocalApp)
            .filter(UserLocalApp.user_id == user_id, UserLocalApp.app_key == app_key)
            .first()
        )
        if existing:
            raise ValueError(f"app_key '{app_key}' already exists for this user")

        # Enforce single default per intent_type
        if fields.get("is_default_for_intent"):
            self._clear_defaults(user_id, fields.get("intent_type", ""))

        app = UserLocalApp(user_id=user_id, **fields)
        self.db.add(app)
        self.db.commit()
        self.db.refresh(app)
        return app

    def update_app(self, app_id: uuid.UUID, user_id: uuid.UUID, **fields: Any) -> UserLocalApp:
        app = self.get_app(app_id, user_id)
        # Enforce single default per intent_type
        new_default = fields.get("is_default_for_intent")
        if new_default and not app.is_default_for_intent:
            self._clear_defaults(user_id, fields.get("intent_type", app.intent_type))
        for key, value in fields.items():
            if value is not None:
                setattr(app, key, value)
        self.db.commit()
        self.db.refresh(app)
        return app

    def delete_app(self, app_id: uuid.UUID, user_id: uuid.UUID) -> None:
        app = self.get_app(app_id, user_id)
        self.db.delete(app)
        self.db.commit()

    # ------------------------------------------------------------------
    # Open (shared between quick-intent and tool paths)
    # ------------------------------------------------------------------

    def open_app(
        self,
        user_id: uuid.UUID,
        *,
        app_key: str | None = None,
        intent_type: str | None = None,
        conversation_id: uuid.UUID | None = None,
        source: str = "api",
    ) -> dict[str, Any]:
        """Launch a local app.

        Resolution order:
        1. If *app_key* is given, find by (user_id, app_key).
        2. Else if *intent_type* is given, find the default app for that intent.
        3. Otherwise return ``not_configured``.

        Returns a dict with keys:
        - status: opened | requires_confirmation | not_configured | requires_selection | failed
        - message: human-readable description
        - app_key, display_name, executable_path
        - pending_action_id (if status == requires_confirmation)
        - candidates (if status == requires_selection)
        - error_detail (if status == failed)
        """
        app: UserLocalApp | None = None

        # ---- Resolve app ----
        if app_key:
            app = (
                self.db.query(UserLocalApp)
                .filter(
                    and_(
                        UserLocalApp.user_id == user_id,
                        UserLocalApp.app_key == app_key,
                        UserLocalApp.enabled.is_(True),
                    )
                )
                .first()
            )
        elif intent_type:
            apps = (
                self.db.query(UserLocalApp)
                .filter(
                    and_(
                        UserLocalApp.user_id == user_id,
                        UserLocalApp.intent_type == intent_type,
                        UserLocalApp.enabled.is_(True),
                    )
                )
                .all()
            )
            if not apps:
                return {
                    "status": "not_configured",
                    "message": f"No enabled app found for intent_type='{intent_type}'.",
                }
            if len(apps) == 1:
                app = apps[0]
            else:
                # Multiple matches — prefer is_default_for_intent
                defaults = [a for a in apps if a.is_default_for_intent]
                if len(defaults) == 1:
                    app = defaults[0]
                else:
                    return {
                        "status": "requires_selection",
                        "message": f"Multiple apps match intent_type='{intent_type}'. Please specify app_key.",
                        "candidates": [_app_to_dict(a) for a in apps],
                    }
        else:
            return {
                "status": "not_configured",
                "message": "Either app_key or intent_type must be provided.",
            }

        if app is None:
            return {
                "status": "not_configured",
                "message": f"No enabled app found for app_key='{app_key}'.",
            }

        # ---- Validate path ----
        path_validation = _validate_executable(app.executable_path)
        if path_validation is not None:
            self._log_action(user_id, conversation_id, app.app_key, "failed",
                             message="Path validation failed", error_detail=path_validation)
            return {
                "status": "failed",
                "message": f"Path validation failed: {path_validation}",
                "app_key": app.app_key,
                "display_name": app.display_name,
                "executable_path": app.executable_path,
                "error_detail": path_validation,
            }

        # ---- Confirmation gate ----
        ext = Path(app.executable_path).suffix.lower()
        needs_confirmation = app.confirm_required or ext in _SCRIPT_EXTENSIONS

        if needs_confirmation and source != "test":
            pending = self._create_pending_action(
                user_id=user_id,
                conversation_id=conversation_id,
                app=app,
            )
            return {
                "status": "requires_confirmation",
                "message": f"Opening '{app.display_name}' requires confirmation.",
                "app_key": app.app_key,
                "display_name": app.display_name,
                "executable_path": app.executable_path,
                "pending_action_id": str(pending.id),
            }

        # ---- Launch ----
        return self._launch_and_log(user_id, conversation_id, app, source)

    def _launch_and_log(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        app: UserLocalApp,
        source: str,
    ) -> dict[str, Any]:
        """Execute the app and write an audit log entry."""
        try:
            args: list[str] = [str(app.executable_path)] + list(app.args_json or [])
            cwd = str(app.working_dir) if app.working_dir else None
            subprocess.Popen(args, cwd=cwd, shell=False)
            self._log_action(user_id, conversation_id, app.app_key, "opened",
                             message=f"Launched via {source}")
            return {
                "status": "opened",
                "message": f"'{app.display_name}' launched successfully.",
                "app_key": app.app_key,
                "display_name": app.display_name,
                "executable_path": app.executable_path,
            }
        except OSError as exc:
            self._log_action(user_id, conversation_id, app.app_key, "failed",
                             message="subprocess.Popen failed", error_detail=str(exc))
            return {
                "status": "failed",
                "message": f"Failed to launch '{app.display_name}': {exc}",
                "app_key": app.app_key,
                "display_name": app.display_name,
                "executable_path": app.executable_path,
                "error_detail": str(exc),
            }

    def execute_pending_action(self, pending_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        """Execute the app associated with a confirmed pending_action."""
        pending = (
            self.db.query(PendingAction)
            .filter(PendingAction.id == pending_id, PendingAction.user_id == user_id)
            .first()
        )
        if pending is None:
            return {"status": "failed", "message": "Pending action not found."}
        if pending.status != "waiting_confirmation":
            return {"status": "failed", "message": f"Pending action already {pending.status}."}

        app_key = pending.payload_json.get("app_key", "")
        app_model_id = pending.payload_json.get("app_model_id")
        app_name = pending.payload_json.get("display_name", app_key)
        app_path = pending.payload_json.get("executable_path", "")

        # Find the app
        app: UserLocalApp | None = None
        if app_model_id:
            try:
                app = (
                    self.db.query(UserLocalApp)
                    .filter(UserLocalApp.id == uuid.UUID(app_model_id))
                    .first()
                )
            except (ValueError, TypeError):
                pass
        if app is None and app_key:
            app = (
                self.db.query(UserLocalApp)
                .filter(
                    and_(
                        UserLocalApp.user_id == user_id,
                        UserLocalApp.app_key == app_key,
                    )
                )
                .first()
            )

        if app is None:
            pending.status = "failed"
            self.db.commit()
            return {
                "status": "failed",
                "message": f"App '{app_key}' no longer exists.",
            }

        # Validate path before launching
        path_validation = _validate_executable(app.executable_path)
        if path_validation is not None:
            pending.status = "failed"
            self.db.commit()
            self._log_action(user_id, pending.conversation_id, app_key, "failed",
                             message="Path validation failed on confirm", error_detail=path_validation)
            return {
                "status": "failed",
                "message": f"Path validation failed: {path_validation}",
                "error_detail": path_validation,
            }

        result = self._launch_and_log(user_id, pending.conversation_id, app, source="confirm")
        if result["status"] == "opened":
            pending.status = "executed"
            pending.executed_at = local_now()
        else:
            pending.status = "failed"
        self.db.commit()
        return result

    def cancel_pending_action(self, pending_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        """Cancel a pending action without executing it."""
        pending = (
            self.db.query(PendingAction)
            .filter(PendingAction.id == pending_id, PendingAction.user_id == user_id)
            .first()
        )
        if pending is None:
            return {"status": "failed", "message": "Pending action not found."}
        if pending.status != "waiting_confirmation":
            return {"status": "failed", "message": f"Pending action already {pending.status}."}

        pending.status = "cancelled"
        pending.cancelled_at = local_now()
        self.db.commit()
        return {"status": "cancelled", "message": "Action cancelled."}

    def get_active_pending_action(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID | None = None
    ) -> PendingAction | None:
        """Return the most recent pending_action that is still waiting for confirmation."""
        q = (
            self.db.query(PendingAction)
            .filter(
                and_(
                    PendingAction.user_id == user_id,
                    PendingAction.status == "waiting_confirmation",
                )
            )
            .order_by(PendingAction.created_at.desc())
        )
        if conversation_id is not None:
            q = q.filter(PendingAction.conversation_id == conversation_id)
        return q.first()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clear_defaults(self, user_id: uuid.UUID, intent_type: str) -> None:
        """Clear is_default_for_intent flag for all apps of the same intent_type."""
        self.db.query(UserLocalApp).filter(
            UserLocalApp.user_id == user_id,
            UserLocalApp.intent_type == intent_type,
            UserLocalApp.is_default_for_intent == True,
        ).update({"is_default_for_intent": False, "updated_at": local_now()})

    def _log_action(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        target: str,
        status: str,
        message: str | None = None,
        error_detail: str | None = None,
    ) -> LocalActionLog:
        log = LocalActionLog(
            user_id=user_id,
            conversation_id=conversation_id,
            action_type="open_local_app",
            target=target,
            status=status,
            message=message,
            error_detail=error_detail,
            finished_at=local_now() if status in ("opened", "failed") else None,
        )
        self.db.add(log)
        self.db.commit()
        return log

    def _create_pending_action(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        app: UserLocalApp,
    ) -> PendingAction:
        pending = PendingAction(
            user_id=user_id,
            conversation_id=conversation_id or uuid.UUID(int=0),  # placeholder; caller should set
            action_type="open_local_app",
            payload_json={
                "app_key": app.app_key,
                "app_model_id": str(app.id),
                "display_name": app.display_name,
                "executable_path": app.executable_path,
                "args_json": app.args_json,
                "working_dir": app.working_dir,
                "intent_type": app.intent_type,
            },
            status="waiting_confirmation",
            expires_at=local_now() + timedelta(minutes=5),
        )
        self.db.add(pending)
        self.db.commit()
        self.db.refresh(pending)
        return pending


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _validate_executable(path_str: str) -> str | None:
    """Return an error message if the path is invalid, else None."""
    p = Path(path_str)
    if not p.exists():
        return f"File does not exist: {path_str}"
    if not p.is_file():
        return f"Path is not a file: {path_str}"
    if os.name == "nt":
        # On Windows, check for a plausible extension
        if not p.suffix:
            return f"No file extension: {path_str}"
    return None


def _app_to_dict(app: UserLocalApp) -> dict[str, Any]:
    return {
        "id": str(app.id),
        "app_key": app.app_key,
        "intent_type": app.intent_type,
        "display_name": app.display_name,
        "executable_path": app.executable_path,
        "working_dir": app.working_dir,
        "args_json": app.args_json,
        "keywords_json": app.keywords_json,
        "enabled": app.enabled,
        "is_default_for_intent": app.is_default_for_intent,
        "confirm_required": app.confirm_required,
    }
