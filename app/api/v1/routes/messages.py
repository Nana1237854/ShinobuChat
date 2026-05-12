from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_chat_service
from app.schemas.message import MessageCreate
from app.services.chat_service import ChatService

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_class=StreamingResponse)
async def create_message(
    payload: MessageCreate,
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    return StreamingResponse(
        chat_service.stream_reply(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
