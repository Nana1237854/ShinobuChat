from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.memory_service import MemoryService
from app.services.sync_service import SyncService


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


def get_memory_service(db: Session = Depends(get_db)) -> MemoryService:
    return MemoryService(db)


def get_sync_service(db: Session = Depends(get_db)) -> SyncService:
    return SyncService(db)
