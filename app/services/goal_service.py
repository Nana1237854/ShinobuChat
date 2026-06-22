from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.user_goal import UserGoal
from app.services.realtime_sync_service import realtime_sync_service

logger = logging.getLogger(__name__)

_GOAL_KEYWORDS = [
    "我想学", "我想做", "我想坚持", "我想完成",
    "我准备找", "我打算", "我希望每天", "我计划",
    "我想养成", "我想开始", "我要学", "我要做",
    "我准备学", "我准备做", "我想考", "我要考",
    "坚持每天", "每天坚持",
]


class GoalService:
    def __init__(self, db: Session):
        self.db = db

    # ---- CRUD ----

    def create_goal(self, user_id: UUID, payload) -> UserGoal:
        now = datetime.now(timezone.utc)
        goal = UserGoal(
            user_id=user_id,
            title=payload.title,
            description=payload.description,
            category=payload.category,
            cadence_days=payload.cadence_days,
            reminder_enabled=payload.reminder_enabled,
            next_check_at=now + timedelta(days=payload.cadence_days),
        )
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def list_goals(self, user_id: UUID, status: str | None = None, include_completed: bool = False):
        query = self.db.query(UserGoal).filter(UserGoal.user_id == user_id)
        if status is not None:
            query = query.filter(UserGoal.status == status)
        elif not include_completed:
            query = query.filter(UserGoal.status != "completed")
        return query.order_by(UserGoal.created_at.desc()).all()

    def update_goal(self, user_id: UUID, goal_id: UUID, payload) -> UserGoal:
        goal = self._get_user_goal(user_id, goal_id)
        now = datetime.now(timezone.utc)
        for key, value in payload.model_dump(exclude_unset=True).items():
            if key == "status" and value is not None:
                goal.status = value
                if value == "paused":
                    goal.paused_at = now
                elif value == "active":
                    goal.paused_at = None
                    if goal.next_check_at is None:
                        goal.next_check_at = now + timedelta(days=goal.cadence_days)
                elif value == "completed":
                    goal.completed_at = now
            elif key == "cadence_days" and value is not None:
                goal.cadence_days = value
                goal.next_check_at = now + timedelta(days=value)
            elif hasattr(goal, key) and value is not None:
                setattr(goal, key, value)
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def delete_goal(self, user_id: UUID, goal_id: UUID) -> None:
        goal = self._get_user_goal(user_id, goal_id)
        self.db.delete(goal)
        self.db.commit()

    # ---- Checkin ----

    def checkin_goal(self, user_id: UUID, goal_id: UUID, note: str | None = None) -> dict:
        goal = self._get_user_goal(user_id, goal_id)
        now = datetime.now(timezone.utc)
        goal.last_checked_at = now
        goal.next_check_at = now + timedelta(days=goal.cadence_days)
        self.db.add(goal)
        self.db.commit()

        payload = self._build_event(goal, "logged")
        self._publish(goal, payload)
        return payload

    # ---- Scanning ----

    def scan_due_checkins(self, now: datetime | None = None) -> list[dict]:
        return self._scan(now)

    def scan_due_checkins_for_user(self, user_id: UUID, now: datetime | None = None) -> list[dict]:
        return self._scan(now, user_id=user_id)

    def _scan(self, now: datetime | None = None, user_id: UUID | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        query = self.db.query(UserGoal).filter(
            UserGoal.status == "active",
            UserGoal.reminder_enabled.is_(True),
            UserGoal.next_check_at.isnot(None),
            UserGoal.next_check_at <= now,
        )
        if user_id is not None:
            query = query.filter(UserGoal.user_id == user_id)

        goals = query.all()
        events: list[dict] = []
        for goal in goals:
            goal.last_checked_at = now
            goal.next_check_at = now + timedelta(days=goal.cadence_days)
            self.db.add(goal)
            payload = self._build_event(goal, "checkin")
            events.append(payload)
            self._publish(goal, payload)
        if events:
            self.db.commit()
        return events

    def _build_event(self, goal: UserGoal, kind: str) -> dict:
        return {
            "type": f"goal.{kind}",
            "goal_id": str(goal.id),
            "user_id": str(goal.user_id),
            "title": goal.title,
            "category": goal.category,
            "status": goal.status,
            "next_check_at": goal.next_check_at.isoformat() if goal.next_check_at else None,
            "message": (
                f"今天要不要简单回顾一下「{goal.title}」的进展？不用有压力，告诉我一点点也可以。"
                if kind == "checkin"
                else f"已记录「{goal.title}」的进度。下次回顾时间已更新。"
            ),
        }

    def _publish(self, goal: UserGoal, payload: dict) -> None:
        try:
            status = realtime_sync_service.status_payload(goal.user_id)
            delivery = "online" if status["online_ios_devices"] > 0 else (
                "apns_queued" if status["ios_push_targets"] > 0 else "no_ios_device"
            )
            payload["delivery"] = delivery
            realtime_sync_service.publish(goal.user_id, f"goal.{payload['type'].split('.', 1)[1] if '.' in payload['type'] else payload['type']}", payload)
            if delivery == "apns_queued":
                realtime_sync_service._queue_apns_notification(goal.user_id, payload)
        except Exception:
            logger.exception("Failed to publish goal event for goal %s", goal.id)

    # ---- Candidate detection ----

    @staticmethod
    def is_goal_candidate(text: str) -> bool:
        return any(keyword in text for keyword in _GOAL_KEYWORDS)

    @staticmethod
    def build_goal_candidate_prompt(text: str) -> str:
        del text
        return "用户表达了可能的长期目标。请先温和询问是否要设为长期目标，不要直接创建或写入数据库。"

    # ---- helpers ----

    def _get_user_goal(self, user_id: UUID, goal_id: UUID) -> UserGoal:
        goal = (
            self.db.query(UserGoal)
            .filter(UserGoal.id == goal_id, UserGoal.user_id == user_id)
            .first()
        )
        if goal is None:
            raise NotFoundError("Goal not found")
        return goal
