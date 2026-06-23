import logging
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.diary import Diary
from app.schemas.diary import DiaryDetail, DiaryGenerateRequest, DiaryGenerateResponse, DiaryOut

logger = logging.getLogger(__name__)


class DiaryService:
    def __init__(self, db: Session):
        self.db = db

    def list_diaries(
        self, user_id: UUID, limit: int = 20, offset: int = 0, mood: str | None = None
    ) -> list[DiaryOut]:
        query = self.db.query(Diary).filter(Diary.user_id == user_id)
        if mood:
            query = query.filter(Diary.mood == mood)
        rows = query.order_by(Diary.date.desc()).offset(offset).limit(limit).all()
        return [DiaryOut.model_validate(row) for row in rows]

    def get_by_date(self, user_id: UUID, diary_date: date) -> DiaryDetail:
        row = (
            self.db.query(Diary)
            .filter(Diary.user_id == user_id, Diary.date == diary_date)
            .first()
        )
        if row is None:
            raise NotFoundError(f"No diary entry for {diary_date}")
        return DiaryDetail.model_validate(row)

    def generate(
        self, user_id: UUID, payload: DiaryGenerateRequest | None = None
    ) -> DiaryGenerateResponse:
        raise NotImplementedError("Diary generation not yet implemented")
