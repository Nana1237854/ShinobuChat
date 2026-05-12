from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.conversation_compactor import ConversationCompactor
from app.services.memory_service import MemoryService
from app.services.sync_service import SyncService
from app.services.todo_service import TodoService


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_memory_service(db: Session = Depends(get_db)) -> MemoryService:
    return MemoryService(db, SyncService(db))


def get_todo_service(db: Session = Depends(get_db)) -> TodoService:
    return TodoService(db, SyncService(db))


def get_agent_orchestrator(
    db: Session = Depends(get_db),
    memory_service: MemoryService = Depends(get_memory_service),
    todo_service: TodoService = Depends(get_todo_service),
) -> AgentOrchestrator:
    return AgentOrchestrator(db, memory_service, todo_service)


def get_compactor() -> ConversationCompactor:
    return ConversationCompactor(max_messages=30, keep_recent=15)


def get_chat_service(
    db: Session = Depends(get_db),
    agent: AgentOrchestrator = Depends(get_agent_orchestrator),
    compactor: ConversationCompactor = Depends(get_compactor),
) -> ChatService:
    return ChatService(db, SyncService(db), agent, compactor)


def get_sync_service(db: Session = Depends(get_db)) -> SyncService:
    return SyncService(db)
