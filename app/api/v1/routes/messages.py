from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_message_service
from app.schemas.message import MessageCreate
from app.services.message_service import MessageService

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_class=StreamingResponse)
def create_message(
    payload: MessageCreate,
    message_service: MessageService = Depends(get_message_service),
) -> StreamingResponse:
    return StreamingResponse(
        message_service.create_streaming_response(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
