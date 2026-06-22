from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_current_user_id, get_memory_service
from app.schemas.memory import (
    MemoryCategory,
    MemoryContextOut,
    MemoryContextMessageOut,
    MemoryCreate,
    MemoryOut,
    MemoryPreferenceOut,
    MemoryPreferenceUpdate,
    MemorySearchHit,
    MemorySearchRequest,
    MemorySearchResultOut,
    MemoryTimelineItemOut,
    MemoryUpdate,
)
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memories", tags=["memories"])


def _time_bucket(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    delta = now - dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else now - dt
    if delta.days < 1:
        return "today"
    if delta.days < 7:
        return "this_week"
    if delta.days < 30:
        return "this_month"
    return "earlier"


def _resolve_conversation_id(memory, db) -> UUID | None:
    """Resolve conversation_id from source_msg_id if available."""
    src = getattr(memory, "source_msg_id", None)
    if src is None:
        return None
    try:
        from app.models.message import Message

        msg = db.query(Message).filter(Message.id == src).first()
        return msg.conversation_id if msg else None
    except Exception:
        return None


def _source_message_summary(content: str, max_chars: int = 100) -> str | None:
    if not content:
        return None
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "..."


# ---- CRUD routes (security: user_id from JWT, not URL param) ----

@router.post("", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryCreate,
    user_id: UUID = Depends(get_current_user_id),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryOut:
    return MemoryOut.model_validate(memory_service.create(payload))


@router.get("/user/me", response_model=list[MemoryOut])
def list_user_memories(
    user_id: UUID = Depends(get_current_user_id),
    category: MemoryCategory | None = None,
    include_archived: bool = False,
    memory_service: MemoryService = Depends(get_memory_service),
) -> list[MemoryOut]:
    return [
        MemoryOut.model_validate(item)
        for item in memory_service.list_by_user(user_id, category, include_archived)
    ]


@router.post("/search", response_model=list[MemorySearchHit])
def search_memories(
    payload: MemorySearchRequest,
    user_id: UUID = Depends(get_current_user_id),
    memory_service: MemoryService = Depends(get_memory_service),
) -> list[MemorySearchHit]:
    payload.user_id = user_id
    return memory_service.search(payload)


@router.get("/settings/me", response_model=MemoryPreferenceOut)
def get_memory_settings(
    user_id: UUID = Depends(get_current_user_id),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryPreferenceOut:
    return MemoryPreferenceOut.model_validate(memory_service.get_preferences(user_id))


@router.patch("/settings/me", response_model=MemoryPreferenceOut)
def update_memory_settings(
    payload: MemoryPreferenceUpdate,
    user_id: UUID = Depends(get_current_user_id),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryPreferenceOut:
    return MemoryPreferenceOut.model_validate(memory_service.update_preferences(user_id, payload))


@router.patch("/{memory_id}", response_model=MemoryOut)
def update_memory(
    memory_id: UUID,
    payload: MemoryUpdate,
    user_id: UUID = Depends(get_current_user_id),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryOut:
    return MemoryOut.model_validate(memory_service.update(memory_id, user_id, payload))


@router.post("/{memory_id}/undo-inference", response_model=MemoryOut)
def undo_memory_inference(
    memory_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryOut:
    return MemoryOut.model_validate(memory_service.undo_inference(memory_id, user_id))


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    memory_service: MemoryService = Depends(get_memory_service),
) -> Response:
    memory_service.delete(memory_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- Timeline / Context / Search API (new) ----

@router.get("/timeline", response_model=list[MemoryTimelineItemOut])
def get_memory_timeline(
    user_id: UUID = Depends(get_current_user_id),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    memory_service: MemoryService = Depends(get_memory_service),
) -> list[MemoryTimelineItemOut]:
    items = memory_service.list_timeline(user_id, limit=limit, offset=offset)
    result: list[MemoryTimelineItemOut] = []
    with memory_service.session_factory() as db:
        for mem in items:
            conv_id = _resolve_conversation_id(mem, db)
            result.append(MemoryTimelineItemOut(
                memory_id=mem.id,
                content=mem.content,
                importance=float(mem.importance),
                created_at=mem.created_at,
                source_msg_id=mem.source_msg_id,
                related_conversation_id=conv_id,
                tags=mem.tags or [],
                time_bucket=_time_bucket(mem.created_at),
            ))
    return result


@router.get("/search", response_model=list[MemorySearchResultOut])
def search_memory_get(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=30),
    user_id: UUID = Depends(get_current_user_id),
    memory_service: MemoryService = Depends(get_memory_service),
) -> list[MemorySearchResultOut]:
    embeddings = memory_service.search_memories(user_id, q, top_k=limit)
    result: list[MemorySearchResultOut] = []
    with memory_service.session_factory() as db:
        for mem in embeddings:
            conv_id = _resolve_conversation_id(mem, db)
            src_summary = None
            if mem.source_msg_id:
                try:
                    from app.models.message import Message
                    msg = db.query(Message).filter(Message.id == mem.source_msg_id).first()
                    if msg:
                        src_summary = _source_message_summary(msg.content)
                except Exception:
                    pass
            result.append(MemorySearchResultOut(
                memory_id=mem.id,
                content=mem.content,
                importance=float(mem.importance),
                created_at=mem.created_at,
                source_msg_id=mem.source_msg_id,
                related_conversation_id=conv_id,
                score=None,
                source_message_summary=src_summary,
            ))
    return result


@router.get("/{memory_id}/context", response_model=MemoryContextOut)
def get_memory_context(
    memory_id: UUID,
    window: int = Query(default=3, ge=1, le=10),
    user_id: UUID = Depends(get_current_user_id),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryContextOut:
    ctx = memory_service.get_memory_context(user_id, memory_id, window=window)
    return MemoryContextOut(
        memory_id=ctx.memory_id,
        source_msg_id=ctx.source_msg_id,
        conversation_id=ctx.conversation_id,
        messages=[MemoryContextMessageOut(
            id=m.id, role=m.role, content=m.content, created_at=m.created_at
        ) for m in ctx.messages],
        detail=ctx.detail,
    )
