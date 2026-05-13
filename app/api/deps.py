from functools import lru_cache
from pathlib import Path

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.agent_service import AgentService
from app.services.ai_client import AIClient
from app.services.auth_service import AuthService
from app.services.conversation_service import ConversationService
from app.services.device_registry_service import DeviceRegistryService
from app.services.http_client import UrllibHttpClient
from app.services.live2d_service import Live2DService
from app.services.message_service import MessageService
from app.services.skill_service import SkillRegistry
from app.services.stream_events import SseEncoder
from app.services.tool_registry import ToolRegistry
from app.services.voice_service import VoiceService


@lru_cache
def get_http_client() -> UrllibHttpClient:
    return UrllibHttpClient()


@lru_cache
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry(Path(__file__).resolve().parents[2] / "skills")


@lru_cache
def get_ai_client() -> AIClient:
    return AIClient(get_http_client())


@lru_cache
def get_agent_service() -> AgentService:
    return AgentService(get_skill_registry())


@lru_cache
def get_tool_registry() -> ToolRegistry:
    return ToolRegistry(get_skill_registry(), get_http_client())


@lru_cache
def get_agent_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(get_agent_service(), get_tool_registry(), get_ai_client())


@lru_cache
def get_sse_encoder() -> SseEncoder:
    return SseEncoder()


@lru_cache
def get_voice_service() -> VoiceService:
    return VoiceService(get_http_client())


@lru_cache
def get_live2d_service() -> Live2DService:
    return Live2DService()


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_device_registry_service(db: Session = Depends(get_db)) -> DeviceRegistryService:
    return DeviceRegistryService(db)


def get_conversation_service(db: Session = Depends(get_db)) -> ConversationService:
    return ConversationService(db)


def get_message_service(db: Session = Depends(get_db)) -> MessageService:
    return MessageService(
        db,
        get_skill_registry(),
        get_agent_service(),
        get_agent_orchestrator(),
        get_ai_client(),
        get_sse_encoder(),
    )
