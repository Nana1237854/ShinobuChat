import logging
from datetime import date, datetime, timezone

import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.diary import Diary
from app.models.user_config import UserConfig
from app.services.config_service import ConfigService
from app.services.diary_service import DiaryService

logger = logging.getLogger(__name__)


class DiarySchedulerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _current_hour_in_timezone(self, timezone_str: str) -> int:
        try:
            tz = pytz.timezone(timezone_str)
            return datetime.now(tz).hour
        except Exception:
            logger.warning("Invalid timezone %s, falling back to UTC", timezone_str)
            return datetime.now(timezone.utc).hour

    def _get_user_auto_diary_enabled(self, config_service: ConfigService, user_id: str) -> bool:
        try:
            val = config_service.get_effective_value(user_id, "auto_diary_enabled")
            return bool(val)
        except Exception:
            return False

    def _get_user_timezone(self, config_service: ConfigService, user_id: str) -> str:
        try:
            val = config_service.get_effective_value(user_id, "auto_diary_timezone")
            return str(val) if val else "Asia/Shanghai"
        except Exception:
            return "Asia/Shanghai"

    def _has_today_diary(self, user_id: str, diary_date: date) -> bool:
        row = self.db.execute(
            select(Diary.id).where(Diary.user_id == user_id, Diary.date == diary_date)
        ).first()
        return row is not None

    def scan_and_generate(self) -> int:
        if not settings.diary_background_scan_interval_seconds:
            return 0

        rows = self.db.execute(
            select(UserConfig.user_id).where(UserConfig.field_name == "auto_diary_enabled")
        ).all()

        generated = 0
        today = date.today()
        target_hour = settings.diary_auto_generate_hour

        for (user_id,) in rows:
            try:
                config_service = ConfigService(self.db)
                if not self._get_user_auto_diary_enabled(config_service, user_id):
                    continue

                tz_str = self._get_user_timezone(config_service, user_id)
                current_hour = self._current_hour_in_timezone(tz_str)

                if current_hour != target_hour:
                    continue

                if self._has_today_diary(user_id, today):
                    continue

                diary_service = DiaryService(
                    self.db,
                    ai_client=None,
                    config_service=config_service,
                    emotion_service=None,
                )

                diary_service.generate(user_id)
                generated += 1
                logger.info("Auto-generated diary for user %s on %s", user_id, today)
            except Exception:
                logger.exception("Failed auto-diary for user %s", user_id)

        return generated
