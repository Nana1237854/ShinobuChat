from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth_service import AuthService
from app.services.conversation_service import ConversationService
from app.services.device_registry_service import DeviceRegistryService
from app.services.memory_service import MemoryService
from app.services.message_service import MessageService
from app.services.sync_service import SyncService


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_device_registry_service(db: Session = Depends(get_db)) -> DeviceRegistryService:
    return DeviceRegistryService(db)


def get_conversation_service(db: Session = Depends(get_db)) -> ConversationService:
    return ConversationService(db)


def get_message_service(db: Session = Depends(get_db)) -> MessageService:
    return MessageService(db)


def get_memory_service(db: Session = Depends(get_db)) -> MemoryService:
    return MemoryService(db)


def get_sync_service(db: Session = Depends(get_db)) -> SyncService:
    return SyncService(db)
