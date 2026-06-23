from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user_id, get_diary_service
from app.core.exceptions import NotFoundError
from app.schemas.diary import DiaryDetail, DiaryGenerateRequest, DiaryGenerateResponse, DiaryOut
from app.services.diary_service import DiaryService

router = APIRouter(prefix="/diaries", tags=["diaries"])


@router.get("", response_model=list[DiaryOut])
def list_diaries(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    mood: str | None = Query(default=None),
    user_id: UUID = Depends(get_current_user_id),
    diary_service: DiaryService = Depends(get_diary_service),
) -> list[DiaryOut]:
    return diary_service.list_diaries(user_id, limit=limit, offset=offset, mood=mood)


@router.get("/{diary_date}", response_model=DiaryDetail)
def get_diary_by_date(
    diary_date: date,
    user_id: UUID = Depends(get_current_user_id),
    diary_service: DiaryService = Depends(get_diary_service),
) -> DiaryDetail:
    try:
        return diary_service.get_by_date(user_id, diary_date)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/generate", response_model=DiaryGenerateResponse, status_code=501)
def generate_diary(
    payload: DiaryGenerateRequest | None = None,
    user_id: UUID = Depends(get_current_user_id),
    diary_service: DiaryService = Depends(get_diary_service),
) -> DiaryGenerateResponse:
    raise HTTPException(status_code=501, detail="Diary generation not yet implemented")
