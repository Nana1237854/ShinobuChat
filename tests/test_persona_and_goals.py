import uuid
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.user import User
from app.services.goal_service import GoalService
from app.services.persona_settings_service import PersonaSettingsService


class PersonaSettingsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="p@t.com", hashed_password="x", display_name="P"))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _svc(self) -> PersonaSettingsService:
        return PersonaSettingsService(self.Session())

    def test_default_settings_when_no_record(self):
        settings = self._svc().get_settings(self.user_id)
        self.assertEqual(settings.verbosity, "balanced")
        self.assertEqual(settings.warmth, "warm")
        self.assertEqual(settings.initiative, "balanced")
        self.assertEqual(settings.work_style, "casual")

    def test_update_and_read_settings(self):
        svc = self._svc()
        from app.schemas.persona import PersonaSettingsUpdate
        svc.update_settings(self.user_id, PersonaSettingsUpdate(verbosity="quiet", warmth="calm"))
        settings = svc.get_settings(self.user_id)
        self.assertEqual(settings.verbosity, "quiet")
        self.assertEqual(settings.warmth, "calm")
        self.assertEqual(settings.initiative, "balanced")  # unchanged
        self.assertEqual(settings.work_style, "casual")    # unchanged

    def test_invalid_enum_rejected(self):
        from app.schemas.persona import PersonaSettingsUpdate
        with self.assertRaises(Exception):
            PersonaSettingsUpdate(verbosity="invalid_value")

    def test_tone_instructions_generated(self):
        svc = self._svc()
        settings = svc.get_settings(self.user_id)
        tone = svc.build_tone_instructions(settings)
        self.assertIn("交流风格", tone)
        self.assertIn("回复适中", tone)
        self.assertIn("语气温柔亲近", tone)

    def test_tone_instructions_not_in_base_system(self):
        """Persona tone must be injected as dynamic context, not modify base_system."""
        svc = self._svc()
        settings = svc.get_settings(self.user_id)
        tone = svc.build_tone_instructions(settings)
        self.assertNotIn("system", tone.lower())
        self.assertNotIn("你是", tone)


class GoalServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        self.other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="g@t.com", hashed_password="x", display_name="G"))
            db.add(User(id=self.other_id, email="o@t.com", hashed_password="x", display_name="O"))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _svc(self) -> GoalService:
        return GoalService(self.Session())

    def _create_payload(self, **overrides):
        class P:
            title = "test goal"
            description = None
            category = None
            cadence_days = 7
            reminder_enabled = True
        for k, v in overrides.items():
            setattr(P, k, v)
        return P()

    def _update_payload(self, **overrides):
        class P:
            def __init__(self):
                self.title = None
                self.description = None
                self.category = None
                self.status = None
                self.cadence_days = None
                self.reminder_enabled = None

            def model_dump(self, exclude_unset=False):
                return {k: v for k, v in vars(self).items() if v is not None}
        p = P()
        for k, v in overrides.items():
            setattr(p, k, v)
        return p

    # 1. Create goal sets next_check_at
    def test_create_goal_sets_next_check_at(self):
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="学日语", cadence_days=7))
        self.assertEqual(goal.title, "学日语")
        self.assertEqual(goal.status, "active")
        self.assertIsNotNone(goal.next_check_at)
        self.assertTrue(goal.reminder_enabled)

    # 2. List goals only returns current user
    def test_list_goals_user_isolation(self):
        svc = self._svc()
        svc.create_goal(self.user_id, self._create_payload(title="mine"))
        svc.create_goal(self.other_id, self._create_payload(title="theirs"))
        mine = svc.list_goals(self.user_id)
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0].title, "mine")

    # 3. Pause goal
    def test_pause_goal(self):
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="暂停测试"))
        updated = svc.update_goal(self.user_id, goal.id, self._update_payload(status="paused"))
        self.assertEqual(updated.status, "paused")
        self.assertIsNotNone(updated.paused_at)

    # 4. Complete goal
    def test_complete_goal(self):
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="完成测试"))
        updated = svc.update_goal(self.user_id, goal.id, self._update_payload(status="completed"))
        self.assertEqual(updated.status, "completed")
        self.assertIsNotNone(updated.completed_at)

    # 5. Resume paused goal
    def test_resume_paused_goal(self):
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="恢复测试"))
        svc.update_goal(self.user_id, goal.id, self._update_payload(status="paused"))
        resumed = svc.update_goal(self.user_id, goal.id, self._update_payload(status="active"))
        self.assertEqual(resumed.status, "active")
        self.assertIsNone(resumed.paused_at)

    # 6. Paused goal does not trigger checkin
    def test_paused_goal_no_checkin(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="已暂停", cadence_days=1))
        svc.update_goal(self.user_id, goal.id, self._update_payload(status="paused"))
        # Force next_check_at to be past
        with self.Session() as db:
            from app.models.user_goal import UserGoal
            g = db.query(UserGoal).filter(UserGoal.id == goal.id).first()
            g.next_check_at = now - timedelta(hours=1)
            db.commit()
        events = svc.scan_due_checkins_for_user(self.user_id, now)
        self.assertEqual(len(events), 0, "paused goal should not trigger checkin")

    # 7. Completed goal does not trigger checkin
    def test_completed_goal_no_checkin(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="已完成", cadence_days=1))
        svc.update_goal(self.user_id, goal.id, self._update_payload(status="completed"))
        with self.Session() as db:
            from app.models.user_goal import UserGoal
            g = db.query(UserGoal).filter(UserGoal.id == goal.id).first()
            g.next_check_at = now - timedelta(hours=1)
            db.commit()
        events = svc.scan_due_checkins_for_user(self.user_id, now)
        self.assertEqual(len(events), 0, "completed goal should not trigger checkin")

    # 8. reminder_enabled=false does not trigger checkin
    def test_disabled_reminder_no_checkin(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="提醒关闭", cadence_days=1, reminder_enabled=False))
        with self.Session() as db:
            from app.models.user_goal import UserGoal
            g = db.query(UserGoal).filter(UserGoal.id == goal.id).first()
            g.next_check_at = now - timedelta(hours=1)
            db.commit()
        events = svc.scan_due_checkins_for_user(self.user_id, now)
        self.assertEqual(len(events), 0, "reminder_enabled=False should not trigger checkin")

    # 9. Active goal triggers checkin when due
    @patch("app.services.goal_service.realtime_sync_service")
    def test_due_goal_triggers_checkin(self, mock_rt):
        mock_rt.status_payload.return_value = {"online_ios_devices": 1, "ios_push_targets": 0}
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="到期目标", cadence_days=1))
        with self.Session() as db:
            from app.models.user_goal import UserGoal
            g = db.query(UserGoal).filter(UserGoal.id == goal.id).first()
            g.next_check_at = now - timedelta(hours=1)
            db.commit()
        events = svc.scan_due_checkins_for_user(self.user_id, now)
        self.assertGreater(len(events), 0)
        self.assertEqual(events[0]["title"], "到期目标")
        self.assertEqual(events[0]["type"], "goal.checkin")
        mock_rt.publish.assert_called()

    # 10. Goal checkin updates next_check_at (debounce)
    def test_checkin_updates_next_check_at(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="防抖测试", cadence_days=7))
        with self.Session() as db:
            from app.models.user_goal import UserGoal
            g = db.query(UserGoal).filter(UserGoal.id == goal.id).first()
            g.next_check_at = now - timedelta(hours=1)
            db.commit()
        events = svc.scan_due_checkins_for_user(self.user_id, now)
        self.assertEqual(len(events), 1)
        # Second scan should produce zero — next_check_at was advanced
        events2 = svc.scan_due_checkins_for_user(self.user_id, now + timedelta(minutes=1))
        self.assertEqual(len(events2), 0, "should not re-fire immediately after checkin")

    # 11. Goal not belonging to user returns 404
    def test_goal_not_found_for_user(self):
        svc = self._svc()
        from app.core.exceptions import NotFoundError
        with self.assertRaises(NotFoundError):
            svc.update_goal(self.user_id, uuid.uuid4(), self._update_payload(status="paused"))

    # 12. Candidate detection
    def test_is_goal_candidate_true(self):
        self.assertTrue(GoalService.is_goal_candidate("我想学日语"))
        self.assertTrue(GoalService.is_goal_candidate("我准备找实习"))
        self.assertTrue(GoalService.is_goal_candidate("我想坚持健身"))
        self.assertTrue(GoalService.is_goal_candidate("我计划每天跑步"))
        self.assertTrue(GoalService.is_goal_candidate("我想养成早起习惯"))

    def test_is_goal_candidate_false(self):
        self.assertFalse(GoalService.is_goal_candidate("今天天气怎么样"))
        self.assertFalse(GoalService.is_goal_candidate("帮我查一下明天温度"))
        self.assertFalse(GoalService.is_goal_candidate("你好"))

    # 13. Goal candidate prompt does not auto-create
    def test_build_goal_candidate_prompt(self):
        prompt = GoalService.build_goal_candidate_prompt("我想学日语")
        self.assertIn("不要直接创建", prompt)

    # 14. Active goal triggers checkin with correct event type
    def test_checkin_goal_user_action(self):
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="手动打卡"))
        result = svc.checkin_goal(self.user_id, goal.id, note="今天学了1小时")
        self.assertEqual(result["type"], "goal.logged")
        self.assertIn("已记录", result["message"])

    # 15. iOS offline writes to APNs outbox
    @patch("app.services.goal_service.realtime_sync_service")
    def test_apns_outbox_for_offline_ios(self, mock_rt):
        mock_rt.status_payload.return_value = {"online_ios_devices": 0, "ios_push_targets": 1}
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="iOS离线", cadence_days=1))
        with self.Session() as db:
            from app.models.user_goal import UserGoal
            g = db.query(UserGoal).filter(UserGoal.id == goal.id).first()
            g.next_check_at = now - timedelta(hours=1)
            db.commit()
        svc.scan_due_checkins_for_user(self.user_id, now)
        mock_rt._queue_apns_notification.assert_called()

    # 16. Scan with no due goals returns empty
    def test_scan_no_due_goals(self):
        now = datetime(2026, 6, 22, 10, 0, 0, tzinfo=timezone.utc)
        svc = self._svc()
        svc.create_goal(self.user_id, self._create_payload(title="未到期", cadence_days=30))
        events = svc.scan_due_checkins_for_user(self.user_id, now)
        self.assertEqual(len(events), 0)

    # 17. Delete goal
    def test_delete_goal(self):
        svc = self._svc()
        goal = svc.create_goal(self.user_id, self._create_payload(title="待删除"))
        svc.delete_goal(self.user_id, goal.id)
        goals = svc.list_goals(self.user_id)
        self.assertEqual(len(goals), 0)


if __name__ == "__main__":
    unittest.main()
