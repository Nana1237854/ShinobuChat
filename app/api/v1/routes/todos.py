from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_todo_service
from app.schemas.sync import TodoOut
from app.services.todo_service import TodoService

router = APIRouter(prefix="/todos", tags=["todos"])


@router.post("", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
def create_todo(
    user_id: UUID,
    title: str,
    notes: str | None = None,
    priority: int = 2,
    todo_service: TodoService = Depends(get_todo_service),
) -> TodoOut:
    todo = todo_service.create(user_id, title, notes=notes, priority=priority)
    return TodoOut.model_validate(todo)


@router.get("/user/{user_id}", response_model=list[TodoOut])
def list_todos(
    user_id: UUID,
    include_completed: bool = False,
    todo_service: TodoService = Depends(get_todo_service),
) -> list[TodoOut]:
    todos = todo_service.list_by_user(user_id, include_completed=include_completed)
    return [TodoOut.model_validate(todo) for todo in todos]


@router.patch("/{todo_id}", response_model=TodoOut)
def update_todo(
    todo_id: UUID,
    user_id: UUID,
    completed: bool | None = None,
    title: str | None = None,
    notes: str | None = None,
    priority: int | None = None,
    todo_service: TodoService = Depends(get_todo_service),
) -> TodoOut:
    todo = todo_service.update(
        todo_id,
        user_id,
        completed=completed,
        title=title,
        notes=notes,
        priority=priority,
    )
    return TodoOut.model_validate(todo)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(
    todo_id: UUID,
    user_id: UUID,
    todo_service: TodoService = Depends(get_todo_service),
) -> None:
    todo_service.delete(todo_id, user_id)
