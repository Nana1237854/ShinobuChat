from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_message_service, get_rate_limiter
from app.core.config import settings
from app.core.rate_limiter import RateLimiter
from app.schemas.message import MessageCreate
from app.services.message_service import MessageService

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_class=StreamingResponse)
async def create_message(
    payload: MessageCreate,
    request: Request,
    message_service: MessageService = Depends(get_message_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> StreamingResponse:
    if settings.rate_limit_enabled:
        rate_limiter.check(f"chat:user:{payload.user_id}", 30, 60)

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
