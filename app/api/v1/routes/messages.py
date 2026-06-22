from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_message_service
from app.schemas.message import MessageCreate
from app.services.message_service import MessageService

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_class=StreamingResponse)
async def create_message(
    payload: MessageCreate,
    request: Request,
    message_service: MessageService = Depends(get_message_service),
) -> StreamingResponse:
    async def event_generator():
        async for sse_chunk in message_service.create_streaming_response(payload):
            if await request.is_disconnected():
                break
            yield sse_chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
