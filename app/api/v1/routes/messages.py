from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_message_service
from app.schemas.message import MessageCreate
from app.services.message_service import MessageService

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_class=StreamingResponse)
async def create_message(
    payload: MessageCreate,
    message_service: MessageService = Depends(get_message_service),
) -> StreamingResponse:
    state = message_service.prepare_stream(payload)
    return StreamingResponse(
        message_service.sse_event_stream(state, payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
