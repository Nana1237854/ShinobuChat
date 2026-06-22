import uuid
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings as _settings
from app.db.session import Base
from app.models.todo import Todo
from app.models.user import User
from app.services.reminder_scheduler_service import ReminderSchedulerService


class ReminderSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        self.other_user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="r@t.com", hashed_password="x", display_name="R"))
            db.add(User(id=self.other_user_id, email="o@t.com", hashed_password="x", display_name="O"))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _service(self, db=None) -> ReminderSchedulerService:
        return ReminderSchedulerService(db or self.Session())

    def _make_todo(self, **overrides) -> Todo:
        defaults = {
            "user_id": self.user_id,
            "title": "test todo",
            "completed": False,
            "priority": 2,
            "reminder_enabled": True,
        }
        defaults.update(overrides)
        return Todo(**defaults)

    # 1. 未到期不提醒
    def test_no_reminder_when_not_due(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        future = now + timedelta(hours=2)
        with self.Session() as db:
            db.add(self._make_todo(due_at=future))
            db.commit()
            events = self._service(db).scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 0)

    # 2. 到期前窗口内提醒 due_soon
    def test_due_soon_within_window(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        due = now + timedelta(minutes=10)  # 10 min < default 15 min window
        with self.Session() as db:
            db.add(self._make_todo(due_at=due, title="即将到期任务"))
            db.commit()
            events = self._service(db).scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].kind, "due_soon")
            self.assertEqual(events[0].title, "即将到期任务")

    # 3. 到期或过期后提醒 due_now
    def test_due_now_when_past_due(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=5)
        with self.Session() as db:
            db.add(self._make_todo(due_at=past, title="已过期任务"))
            db.commit()
            events = self._service(db).scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].kind, "due_now")
            self.assertEqual(events[0].title, "已过期任务")

    # 4. 已提醒过不重复刷屏
    def test_no_duplicate_same_kind(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        due = now + timedelta(minutes=5)
        with self.Session() as db:
            db.add(self._make_todo(
                due_at=due,
                last_reminded_at=now - timedelta(minutes=2),
                last_reminder_kind="due_soon",
            ))
            db.commit()
            events = self._service(db).scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 0, "should not re-fire same kind")

    # 4b. due_soon 已发，过期后 due_now 可以再发（类型不同）
    def test_due_now_fires_after_due_soon(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=10)
        with self.Session() as db:
            db.add(self._make_todo(
                due_at=past,
                last_reminded_at=now - timedelta(minutes=20),
                last_reminder_kind="due_soon",
            ))
            db.commit()
            events = self._service(db).scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].kind, "due_now")

    # 5. snooze 后延迟提醒
    def test_snooze_delays_reminder(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=30)
        with self.Session() as db:
            todo = self._make_todo(due_at=past, title="稍后提醒任务")
            db.add(todo)
            db.commit()
            svc = self._service(db)
            event = svc.snooze(self.user_id, todo.id, minutes=15, now=now)
            self.assertIsNotNone(event)
            self.assertEqual(event.kind, "snoozed")

            # Immediately after snooze, no reminder
            events = svc.scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 0, "should not fire while snoozed")

            # After snooze expiry, should fire
            after_snooze = now + timedelta(minutes=20)
            events = svc.scan_due_reminders_for_user(self.user_id, after_snooze)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].kind, "due_now")

    # 6. dismiss 后不再提醒
    def test_dismiss_stops_reminders(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=30)
        with self.Session() as db:
            todo = self._make_todo(due_at=past, title="已忽略任务")
            db.add(todo)
            db.commit()
            svc = self._service(db)
            event = svc.dismiss(self.user_id, todo.id)
            self.assertIsNotNone(event)
            self.assertEqual(event.kind, "dismissed")

            # After dismiss, no reminder
            events = svc.scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 0, "should not fire after dismiss")

    # 7. 已完成 Todo 不提醒
    def test_completed_todo_no_reminder(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=10)
        with self.Session() as db:
            db.add(self._make_todo(due_at=past, completed=True))
            db.commit()
            events = self._service(db).scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 0)

    # 8. 无 due_at 不提醒
    def test_no_due_at_no_reminder(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        with self.Session() as db:
            db.add(self._make_todo(due_at=None))
            db.commit()
            events = self._service(db).scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 0)

    # 9. 只能操作当前用户自己的 Todo
    def test_user_isolation_for_snooze(self):
        with self.Session() as db:
            todo = self._make_todo(user_id=self.other_user_id, due_at=datetime.now(timezone.utc))
            db.add(todo)
            db.commit()
            event = self._service(db).snooze(self.user_id, todo.id, minutes=10)
            self.assertIsNone(event, "should not snooze another user's todo")

    def test_user_isolation_for_dismiss(self):
        with self.Session() as db:
            todo = self._make_todo(user_id=self.other_user_id, due_at=datetime.now(timezone.utc))
            db.add(todo)
            db.commit()
            event = self._service(db).dismiss(self.user_id, todo.id)
            self.assertIsNone(event, "should not dismiss another user's todo")

    def test_user_isolation_for_scan(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=30)
        with self.Session() as db:
            db.add(self._make_todo(user_id=self.other_user_id, due_at=past))
            db.commit()
            events = self._service(db).scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 0, "should not see other user's todos")

    # 10. SSE publish 被调用
    @patch("app.services.reminder_scheduler_service.realtime_sync_service")
    def test_publish_called_on_due_event(self, mock_rt):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=10)
        mock_rt.status_payload.return_value = {
            "online_ios_devices": 1,
            "ios_push_targets": 0,
        }
        with self.Session() as db:
            db.add(self._make_todo(due_at=past, title="推送测试"))
            db.commit()
            self._service(db).scan_due_reminders_for_user(self.user_id, now)
            mock_rt.publish.assert_called()
            call_args = mock_rt.publish.call_args
            self.assertEqual(call_args[0][0], self.user_id)
            self.assertIn("reminder.due_now", call_args[0][1])

    # 11. 离线 iOS 写入 APNs outbox
    @patch("app.services.reminder_scheduler_service.realtime_sync_service")
    def test_apns_outbox_for_offline_ios(self, mock_rt):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=10)
        mock_rt.status_payload.return_value = {
            "online_ios_devices": 0,
            "ios_push_targets": 1,
        }
        with self.Session() as db:
            db.add(self._make_todo(due_at=past, title="离线 iOS"))
            db.commit()
            self._service(db).scan_due_reminders_for_user(self.user_id, now)
            mock_rt._queue_apns_notification.assert_called()

    # 12. reminder_enabled=False 不提醒
    def test_disabled_reminder_no_fire(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=10)
        with self.Session() as db:
            db.add(self._make_todo(due_at=past, reminder_enabled=False))
            db.commit()
            events = self._service(db).scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 0)

    # 13. ReminderEvent.to_payload 格式
    def test_event_payload_format(self):
        from app.services.reminder_scheduler_service import ReminderEvent

        now = datetime.now(timezone.utc)
        event = ReminderEvent(
            todo_id=uuid.uuid4(),
            user_id=self.user_id,
            kind="due_now",
            title="测试任务",
            due_at=now,
            message="该做测试任务了",
            reminder_count=1,
        )
        payload = event.to_payload()
        self.assertEqual(payload["type"], "reminder.due_now")
        self.assertEqual(payload["title"], "测试任务")
        self.assertEqual(payload["reminder_count"], 1)
        self.assertIn("due_at", payload)

    # 14. scan_due_reminders（全局扫描）
    def test_scan_all_users(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=10)
        with self.Session() as db:
            db.add(self._make_todo(user_id=self.user_id, due_at=past, title="用户1"))
            db.add(self._make_todo(user_id=self.other_user_id, due_at=past, title="用户2"))
            db.commit()
            events = self._service(db).scan_due_reminders(now)
            self.assertEqual(len(events), 2)

    # 15. reminder_enabled setting 控制
    @patch("app.services.reminder_scheduler_service.settings")
    def test_reminder_disabled_globally(self, mock_settings):
        mock_settings.reminder_enabled = False
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(minutes=10)
        with self.Session() as db:
            db.add(self._make_todo(due_at=past))
            db.commit()
            events = self._service(db).scan_due_reminders_for_user(self.user_id, now)
            self.assertEqual(len(events), 0)


if __name__ == "__main__":
    unittest.main()
