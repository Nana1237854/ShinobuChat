from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import get_current_user_id

router = APIRouter(prefix="/vision", tags=["vision"])


@router.post("/analyze", status_code=501)
def analyze_image(
    file: UploadFile = File(...),
    question: str | None = Form(None),
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    raise HTTPException(status_code=501, detail="Vision analysis not yet implemented")
