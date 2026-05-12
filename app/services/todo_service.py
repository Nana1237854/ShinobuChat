from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db_utils import require_user
from app.models.todo import Todo
from app.schemas.sync import TodoOut
from app.services.realtime_sync_service import realtime_sync_service
from app.services.sync_service import SyncService


class TodoService:
    def __init__(self, db: Session, sync: SyncService):
        self.db = db
        self.sync = sync

    def create(
        self,
        user_id: UUID,
        title: str,
        *,
        notes: str | None = None,
        priority: int = 2,
        due_at: datetime | None = None,
    ) -> Todo:
        require_user(self.db, user_id)
        todo = Todo(
            user_id=user_id,
            title=title.strip(),
            notes=notes.strip() if notes else None,
            priority=priority,
            due_at=due_at,
        )
        self.db.add(todo)
        self.db.commit()
        self.db.refresh(todo)
        self.sync.record_server_change(
            user_id,
            "todos",
            todo.id,
            "upsert",
            TodoOut.model_validate(todo).model_dump(mode="json"),
            todo.updated_at,
        )
        realtime_sync_service.publish(
            user_id,
            "todo.created",
            {"todo": TodoOut.model_validate(todo).model_dump(mode="json")},
        )
        return todo

    def list_by_user(self, user_id: UUID, *, include_completed: bool = False) -> list[Todo]:
        require_user(self.db, user_id)
        query = self.db.query(Todo).filter(Todo.user_id == user_id)
        if not include_completed:
            query = query.filter(Todo.completed.is_(False))
        return query.order_by(
            Todo.priority.desc(),
            Todo.due_at.asc().nullslast(),
            Todo.created_at.desc(),
        ).all()

    def get_for_user(self, todo_id: UUID, user_id: UUID) -> Todo:
        todo = self.db.query(Todo).filter(Todo.id == todo_id, Todo.user_id == user_id).first()
        if not todo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
        return todo

    def update(self, todo_id: UUID, user_id: UUID, **fields) -> Todo:
        todo = self.get_for_user(todo_id, user_id)
        for key, value in fields.items():
            if value is not None and hasattr(todo, key):
                setattr(todo, key, value.strip() if isinstance(value, str) else value)
        todo.updated_at = datetime.utcnow()
        self.db.add(todo)
        self.db.commit()
        self.db.refresh(todo)
        self.sync.record_server_change(
            user_id,
            "todos",
            todo.id,
            "upsert",
            TodoOut.model_validate(todo).model_dump(mode="json"),
            todo.updated_at,
        )
        realtime_sync_service.publish(
            user_id,
            "todo.updated",
            {"todo": TodoOut.model_validate(todo).model_dump(mode="json")},
        )
        return todo

    def delete(self, todo_id: UUID, user_id: UUID) -> None:
        todo = self.get_for_user(todo_id, user_id)
        payload = TodoOut.model_validate(todo).model_dump(mode="json")
        self.sync.record_server_change(user_id, "todos", todo.id, "delete", payload, datetime.utcnow())
        self.db.delete(todo)
        self.db.commit()
        realtime_sync_service.publish(user_id, "todo.deleted", {"todo": payload})
