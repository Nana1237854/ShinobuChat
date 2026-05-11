import queue
from uuid import UUID

import anyio
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.sync import (
    ApnsRegistrationRequest,
    ApnsRegistrationResponse,
    SyncStatusOut,
)
from app.services.realtime_sync_service import realtime_sync_service

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/events", response_class=StreamingResponse)
async def sync_events(
    user_id: UUID,
    device_id: str = Query(min_length=1, max_length=128),
    device_type: str = Query(default="web", pattern="^(web|ios|unknown)$"),
) -> StreamingResponse:
    subscription = realtime_sync_service.connect(user_id, device_id, device_type)

    async def event_stream():
        try:
            while True:
                try:
                    event = await anyio.to_thread.run_sync(
                        subscription.events.get,
                        True,
                        settings.sync_heartbeat_seconds,
                    )
                except queue.Empty:
                    event = realtime_sync_service.heartbeat_event(user_id)
                yield realtime_sync_service.format_sse(event)
        finally:
            realtime_sync_service.disconnect(subscription)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.websocket("/ws")
async def sync_websocket(
    websocket: WebSocket,
    user_id: UUID,
    device_id: str,
    device_type: str = "unknown",
) -> None:
    await websocket.accept()
    subscription = realtime_sync_service.connect(user_id, device_id, device_type)
    try:
        while True:
            try:
                event = await anyio.to_thread.run_sync(
                    subscription.events.get,
                    True,
                    settings.sync_heartbeat_seconds,
                )
            except queue.Empty:
                event = realtime_sync_service.heartbeat_event(user_id)
            await websocket.send_json(event)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        realtime_sync_service.disconnect(subscription)


@router.post("/apns/register", response_model=ApnsRegistrationResponse)
def register_apns_target(payload: ApnsRegistrationRequest) -> ApnsRegistrationResponse:
    target = realtime_sync_service.register_apns_target(
        user_id=payload.user_id,
        device_token=payload.device_token,
        device_name=payload.device_name,
    )
    return ApnsRegistrationResponse(
        user_id=target.user_id,
        device_name=target.device_name,
        registered_at=target.registered_at,
        sandbox=settings.apns_sandbox,
    )


@router.get("/status/{user_id}", response_model=SyncStatusOut)
def sync_status(user_id: UUID) -> SyncStatusOut:
    return SyncStatusOut.model_validate(realtime_sync_service.status_payload(user_id))
