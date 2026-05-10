from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth_service import AuthService
from app.services.conversation_service import ConversationService
from app.services.device_registry_service import DeviceRegistryService
from app.services.message_service import MessageService


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_device_registry_service(db: Session = Depends(get_db)) -> DeviceRegistryService:
    return DeviceRegistryService(db)


def get_conversation_service(db: Session = Depends(get_db)) -> ConversationService:
    return ConversationService(db)


def get_message_service(db: Session = Depends(get_db)) -> MessageService:
    return MessageService(db)
