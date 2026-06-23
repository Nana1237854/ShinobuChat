from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from app.api.deps import get_current_user_id, get_diary_service, rate_limit_user
from app.core.exceptions import BadRequestError, NotFoundError
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


@router.post("/generate", response_model=DiaryGenerateResponse)
def generate_diary(
    payload: DiaryGenerateRequest | None = None,
    user_id: UUID = Depends(get_current_user_id),
    diary_service: DiaryService = Depends(get_diary_service),
    _: None = Depends(rate_limit_user("diary", 5, 60)),
) -> DiaryGenerateResponse:
    try:
        return diary_service.generate(user_id, payload)
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/export", response_class=PlainTextResponse)
def export_diaries(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    fmt: str = Query(default="markdown", alias="format"),
    user_id: UUID = Depends(get_current_user_id),
    diary_service: DiaryService = Depends(get_diary_service),
) -> PlainTextResponse:
    delta = to_date - from_date
    if delta.days < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="from date must be before to date")
    if delta.days > 365:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date range cannot exceed 365 days")

    diaries = diary_service.list_diaries_in_range(user_id, from_date, to_date)
    if not diaries:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No diaries in this range")

    lines = ["# Shinobu Diary Export", f"# {from_date} ~ {to_date}", ""]
    for d in diaries:
        lines.append(f"## {d.date} — {d.title}")
        if d.mood:
            lines.append(f"**Mood:** {d.mood}")
        lines.append("")
        lines.append(d.content or d.summary)
        lines.append("")
        lines.append("---")
        lines.append("")

    filename = f"shinobu-diaries-{from_date.isoformat()}-{to_date.isoformat()}.md"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return PlainTextResponse(
        "\n".join(lines),
        media_type="text/markdown; charset=utf-8",
        headers=headers,
    )
