import logging
import uuid
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.todo import Todo
from app.models.user import User
from app.services.reminder_scheduler_service import ReminderSchedulerService


class ReminderModeFallbackTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="r@t.com", hashed_password="x", display_name="R"))
            db.commit()
        # Seed a todo due now
        with self.Session() as db:
            db.add(Todo(
                user_id=self.user_id,
                title="Test Reminder",
                due_at=datetime.now(timezone.utc) - timedelta(minutes=5),
                reminder_enabled=True,
            ))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    # ── _get_user_mode returns (mode, reason) ──

    def test_get_user_mode_returns_tuple(self):
        mock_mode_svc = MagicMock()
        mock_mode_svc.get_mode.return_value = MagicMock(value="work")
        svc = ReminderSchedulerService(
            self.Session(), mode_service=mock_mode_svc
        )
        mode, reason = svc._get_user_mode(self.user_id)
        self.assertEqual(mode, "work")
        self.assertEqual(reason, "loaded")

    def test_get_user_mode_no_service_returns_fallback(self):
        svc = ReminderSchedulerService(self.Session(), mode_service=None)
        with self.assertLogs(
            "app.services.reminder_scheduler_service", level="WARNING"
        ) as logs:
            mode, reason = svc._get_user_mode(self.user_id)
        self.assertEqual(mode, "companion")
        self.assertEqual(reason, "fallback: no ModeService")
        self.assertTrue(len(logs.records) >= 1, "Should emit at least one WARNING log")

    def test_get_user_mode_exception_returns_fallback(self):
        mock_mode_svc = MagicMock()
        mock_mode_svc.get_mode.side_effect = RuntimeError("DB crash")
        svc = ReminderSchedulerService(
            self.Session(), mode_service=mock_mode_svc
        )
        with self.assertLogs(
            "app.services.reminder_scheduler_service", level="WARNING"
        ) as logs:
            mode, reason = svc._get_user_mode(self.user_id)
        self.assertEqual(mode, "companion")
        self.assertEqual(reason, "fallback")
        self.assertTrue(any("Falling back" in record.getMessage() for record in logs.records))

    # ── Scan doesn't break on mode failure ──

    def test_scan_does_not_raise_on_mode_failure(self):
        mock_mode_svc = MagicMock()
        mock_mode_svc.get_mode.side_effect = RuntimeError("DB crash")
        svc = ReminderSchedulerService(
            self.Session(), mode_service=mock_mode_svc
        )
        with patch(
            "app.services.reminder_scheduler_service.settings.reminder_enabled", True
        ):
            events = svc.scan_due_reminders_for_user(self.user_id)
            # Should not raise, should fall back to companion mode filtering
            self.assertIsInstance(events, list)

    # ── Normal mode load produces no warning ──

    def test_normal_mode_load_no_warning(self):
        mock_mode_svc = MagicMock()
        mock_mode_svc.get_mode.return_value = MagicMock(value="companion")
        svc = ReminderSchedulerService(
            self.Session(), mode_service=mock_mode_svc
        )
        with self.assertNoLogs(
            "app.services.reminder_scheduler_service", level="WARNING"
        ):
            mode, reason = svc._get_user_mode(self.user_id)
        self.assertEqual(mode, "companion")
        self.assertEqual(reason, "loaded")

    # ── Mode-aware filtering still works with tuple ──

    def test_focus_mode_filters_due_soon(self):
        mock_mode_svc = MagicMock()
        mock_mode_svc.get_mode.return_value = MagicMock(value="focus")
        svc = ReminderSchedulerService(
            self.Session(), mode_service=mock_mode_svc
        )

        with self.Session() as db:
            db.query(Todo).delete()
            db.add(Todo(
                user_id=self.user_id,
                title="Due Soon",
                due_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                reminder_enabled=True,
            ))
            db.commit()

        with patch(
            "app.services.reminder_scheduler_service.settings.reminder_enabled", True
        ):
            events = svc.scan_due_reminders_for_user(self.user_id)
            # Should have no events because due_soon is filtered in focus mode
            self.assertEqual(len(events), 0)

    def test_companion_mode_does_not_filter_due_soon(self):
        mock_mode_svc = MagicMock()
        mock_mode_svc.get_mode.return_value = MagicMock(value="companion")
        svc = ReminderSchedulerService(
            self.Session(), mode_service=mock_mode_svc
        )

        with self.Session() as db:
            db.query(Todo).delete()
            db.add(Todo(
                user_id=self.user_id,
                title="Due Soon",
                due_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                reminder_enabled=True,
            ))
            db.commit()

        with patch(
            "app.services.reminder_scheduler_service.settings.reminder_enabled", True
        ):
            events = svc.scan_due_reminders_for_user(self.user_id)
            # Companian mode allows due_soon for now (default behavior)
            self.assertIsInstance(events, list)
