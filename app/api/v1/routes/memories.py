from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_memory_service
from app.schemas.memory import MemoryCreate, MemoryOut, MemoryUpdate
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
    memory_service: MemoryService = Depends(get_memory_service),
) -> list[MemoryOut]:
    return [MemoryOut.model_validate(item) for item in memory_service.list_by_user(user_id)]


@router.patch("/{memory_id}", response_model=MemoryOut)
def update_memory(
    memory_id: UUID,
    user_id: UUID,
    payload: MemoryUpdate,
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryOut:
    return MemoryOut.model_validate(memory_service.update(memory_id, user_id, payload))


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: UUID,
    user_id: UUID,
    memory_service: MemoryService = Depends(get_memory_service),
) -> Response:
    memory_service.delete(memory_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
