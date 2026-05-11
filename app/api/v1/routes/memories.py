from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_memory_service
from app.schemas.memory import (
    MemoryCategory,
    MemoryCreate,
    MemoryOut,
    MemoryPreferenceOut,
    MemoryPreferenceUpdate,
    MemorySearchHit,
    MemorySearchRequest,
    MemoryUpdate,
)
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memories", tags=["memories"])


@router.post("", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryCreate,
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryOut:
    return MemoryOut.model_validate(memory_service.create(payload))


@router.get("/user/{user_id}", response_model=list[MemoryOut])
def list_user_memories(
    user_id: UUID,
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
    memory_service: MemoryService = Depends(get_memory_service),
) -> list[MemorySearchHit]:
    return memory_service.search(payload)


@router.get("/settings/{user_id}", response_model=MemoryPreferenceOut)
def get_memory_settings(
    user_id: UUID,
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryPreferenceOut:
    return MemoryPreferenceOut.model_validate(memory_service.get_preferences(user_id))


@router.patch("/settings/{user_id}", response_model=MemoryPreferenceOut)
def update_memory_settings(
    user_id: UUID,
    payload: MemoryPreferenceUpdate,
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryPreferenceOut:
    return MemoryPreferenceOut.model_validate(memory_service.update_preferences(user_id, payload))


@router.patch("/{memory_id}", response_model=MemoryOut)
def update_memory(
    memory_id: UUID,
    user_id: UUID,
    payload: MemoryUpdate,
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryOut:
    return MemoryOut.model_validate(memory_service.update(memory_id, user_id, payload))


@router.post("/{memory_id}/undo-inference", response_model=MemoryOut)
def undo_memory_inference(
    memory_id: UUID,
    user_id: UUID = Query(...),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryOut:
    return MemoryOut.model_validate(memory_service.undo_inference(memory_id, user_id))


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: UUID,
    user_id: UUID,
    memory_service: MemoryService = Depends(get_memory_service),
) -> Response:
    memory_service.delete(memory_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
