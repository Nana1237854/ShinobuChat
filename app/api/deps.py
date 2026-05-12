from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.auth_service import AuthService
from app.services.character_service import CharacterService
from app.services.chat_service import ChatService
from app.services.conversation_compactor import ConversationCompactor
from app.services.decision_service import DecisionService
from app.services.memory_service import MemoryService
from app.services.message_service import MessageService
from app.services.roleplay_service import RoleplayService
from app.services.skill_service import SkillService
from app.services.sync_service import SyncService
from app.services.todo_service import TodoService


_character_service: CharacterService | None = None
_decision_service: DecisionService | None = None
_roleplay_service: RoleplayService | None = None
_skill_service: SkillService | None = None


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


def get_message_service(db: Session = Depends(get_db)) -> MessageService:
    return MessageService(db)


def get_sync_service(db: Session = Depends(get_db)) -> SyncService:
    return SyncService(db)


def get_character_service() -> CharacterService:
    global _character_service
    if _character_service is None:
        _character_service = CharacterService()
    return _character_service


def get_decision_service() -> DecisionService:
    global _decision_service
    if _decision_service is None:
        _decision_service = DecisionService()
    return _decision_service


def get_roleplay_service() -> RoleplayService:
    global _roleplay_service
    if _roleplay_service is None:
        _roleplay_service = RoleplayService()
    return _roleplay_service


def get_skill_service() -> SkillService:
    global _skill_service
    if _skill_service is None:
        _skill_service = SkillService()
    return _skill_service
