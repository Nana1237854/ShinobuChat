from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.todo import Todo
from app.services.realtime_sync_service import realtime_sync_service

logger = logging.getLogger(__name__)

REMINDER_KINDS = ("due_soon", "due_now", "snoozed", "dismissed")


@dataclass
class ReminderEvent:
    todo_id: UUID
    user_id: UUID
    kind: str
    title: str
    due_at: datetime | None
    message: str
    reminder_count: int
    delivery: str = "no_ios_device"

    def to_payload(self) -> dict:
        return {
            "type": f"reminder.{self.kind}",
            "todo_id": str(self.todo_id),
            "user_id": str(self.user_id),
            "title": self.title,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "message": self.message,
            "reminder_count": self.reminder_count,
            "delivery": self.delivery,
        }


class ReminderSchedulerService:
    def __init__(self, db: Session, mode_service=None):
        self.db = db
        self._mode_service = mode_service

    def _get_user_mode(self, user_id: UUID) -> tuple[str, str]:
        """Return (mode, reason) — logs a warning when fallback is used."""
        if self._mode_service is None:
            logger.warning(
                "ModeService unavailable for reminders user_id=%s, falling back to companion",
                user_id,
            )
            return "companion", "fallback: no ModeService"

        try:
            mode = self._mode_service.get_mode(user_id)
            return mode.value, "loaded"
        except Exception as exc:
            logger.warning(
                "Falling back to companion mode for reminders user_id=%s: %s",
                user_id,
                exc,
            )
            return "companion", "fallback"

    # ---- scanning ----

    def scan_due_reminders(
        self, now: datetime | None = None
    ) -> list[ReminderEvent]:
        """Scan all users' incomplete todos for due reminders (background task)."""
        return self._scan(now)

    def scan_due_reminders_for_user(
        self, user_id: UUID, now: datetime | None = None
    ) -> list[ReminderEvent]:
        """Scan one user's incomplete todos (API endpoint)."""
        return self._scan(now, user_id=user_id)

    def _scan(
        self,
        now: datetime | None = None,
        user_id: UUID | None = None,
    ) -> list[ReminderEvent]:
        if not settings.reminder_enabled:
            return []

        now = now or datetime.now(timezone.utc)
        due_soon_window = timedelta(minutes=settings.reminder_due_soon_minutes)

        query = self.db.query(Todo).filter(
            Todo.completed.is_(False),
            Todo.due_at.isnot(None),
            Todo.reminder_enabled.is_(True),
            Todo.dismissed_at.is_(None),
        )
        if user_id is not None:
            query = query.filter(Todo.user_id == user_id)

        candidates = query.all()
        events: list[ReminderEvent] = []

        for todo in candidates:
            event = self._evaluate(todo, now, due_soon_window)
            if event is not None:
                events.append(event)
                todo.last_reminded_at = now
                todo.last_reminder_kind = event.kind
                todo.reminder_count += 1
                self.db.add(todo)

                self._publish(todo, event)

        if events:
            self.db.commit()
        return events

    def _evaluate(
        self,
        todo: Todo,
        now: datetime,
        due_soon_window: timedelta,
    ) -> ReminderEvent | None:
        due_at = todo.due_at
        if due_at is None:
            return None

        # Normalize timezone
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)

        # Snoozed
        if todo.snoozed_until is not None:
            snoozed = todo.snoozed_until
            if snoozed.tzinfo is None:
                snoozed = snoozed.replace(tzinfo=timezone.utc)
            if snoozed > now:
                return None

        kind = None
        if due_at <= now:
            kind = "due_now"
        elif due_at - now <= due_soon_window:
            kind = "due_soon"

        if kind is None:
            return None

        # Mode-aware filtering
        user_mode, _mode_reason = self._get_user_mode(todo.user_id)
        if user_mode in ("focus", "night") and kind == "due_soon":
            return None  # Only urgent reminders in focus/night mode
        if user_mode == "focus" and todo.priority and todo.priority < 2 and kind == "due_now":
            return None  # In focus mode, only remind high-priority items

        # Debounce: skip if same kind already sent (unless snooze expired)
        if todo.last_reminder_kind == kind and todo.last_reminded_at is not None:
            return None

        # Mode-aware message tone
        message = self._build_reminder_message(todo.title, kind, user_mode)
        return ReminderEvent(
            todo_id=todo.id,
            user_id=todo.user_id,
            kind=kind,
            title=todo.title,
            due_at=todo.due_at,
            message=message,
            reminder_count=todo.reminder_count + 1,
        )

    def _build_reminder_message(self, title: str, kind: str, mode: str) -> str:
        if mode == "work":
            return (
                f"任务「{title}」已到期，请尽快完成。"
                if kind == "due_now"
                else f"提示：「{title}」将在 {settings.reminder_due_soon_minutes} 分钟内到期，请安排时间。"
            )
        if mode == "focus":
            return f"「{title}」到期。"
        if mode == "night":
            return (
                f"{title} — 该休息了，明天再处理吧。"
                if kind == "due_now"
                else f"提醒：「{title}」快到期了。"
            )
        # companion / default
        return (
            f"任务「{title}」已到期，记得完成哦。"
            if kind == "due_now"
            else f"任务「{title}」将在 {settings.reminder_due_soon_minutes} 分钟内到期。"
        )

    # ---- snooze / dismiss ----

    def snooze(
        self, user_id: UUID, todo_id: UUID, minutes: int = 10, now: datetime | None = None
    ) -> ReminderEvent | None:
        todo = self._get_user_todo(user_id, todo_id)
        if todo is None:
            return None
        now = now or datetime.now(timezone.utc)
        todo.snoozed_until = now + timedelta(minutes=max(1, minutes))
        todo.last_reminder_kind = "snoozed"
        todo.last_reminded_at = now
        todo.dismissed_at = None
        self.db.add(todo)
        self.db.commit()

        event = ReminderEvent(
            todo_id=todo.id,
            user_id=todo.user_id,
            kind="snoozed",
            title=todo.title,
            due_at=todo.due_at,
            message=f"「{todo.title}」已延迟提醒 {minutes} 分钟。",
            reminder_count=todo.reminder_count,
        )
        self._publish(todo, event)
        return event

    def dismiss(self, user_id: UUID, todo_id: UUID) -> ReminderEvent | None:
        todo = self._get_user_todo(user_id, todo_id)
        if todo is None:
            return None
        now = datetime.now(timezone.utc)
        todo.dismissed_at = now
        todo.last_reminder_kind = "dismissed"
        todo.last_reminded_at = now
        todo.snoozed_until = None
        self.db.add(todo)
        self.db.commit()

        event = ReminderEvent(
            todo_id=todo.id,
            user_id=todo.user_id,
            kind="dismissed",
            title=todo.title,
            due_at=todo.due_at,
            message=f"「{todo.title}」的提醒已关闭。",
            reminder_count=todo.reminder_count,
        )
        self._publish(todo, event)
        return event

    # ---- helpers ----

    def _get_user_todo(self, user_id: UUID, todo_id: UUID) -> Todo | None:
        return (
            self.db.query(Todo)
            .filter(Todo.id == todo_id, Todo.user_id == user_id)
            .first()
        )

    def _publish(self, todo: Todo, event: ReminderEvent) -> None:
        status = realtime_sync_service.status_payload(todo.user_id)
        if status["online_ios_devices"] > 0:
            event.delivery = "online"
        elif status["ios_push_targets"] > 0:
            event.delivery = "apns_queued"
        else:
            event.delivery = "no_ios_device"

        payload = event.to_payload()
        try:
            realtime_sync_service.publish(
                todo.user_id,
                f"reminder.{event.kind}",
                payload,
            )
            if event.delivery == "apns_queued":
                realtime_sync_service._queue_apns_notification(
                    todo.user_id, payload
                )
        except Exception:
            logger.exception(
                "Failed to publish reminder event for todo %s", todo.id
            )
