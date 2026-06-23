from functools import lru_cache
from pathlib import Path
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.agent_service import AgentService
from app.services.agents import AgentCoordinator, ChatAgent, MemoryAgent, RouterAgent, TaskAgent
from app.services.ai_client import AIClient
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.character_service import CharacterService
from app.services.conversation_compactor import ConversationCompactor
from app.services.config_service import ConfigService
from app.services.conversation_service import ConversationService
from app.services.device_registry_service import DeviceRegistryService
from app.services.embedding_service import EmbeddingService
from app.services.http_client import UrllibHttpClient
from app.services.character_profile_service import CharacterProfileService
from app.services.diary_service import DiaryService
from app.services.image_understanding_service import ImageUnderstandingService
from app.services.live2d_interaction_service import Live2DInteractionService
from app.services.live2d_service import Live2DService
from app.services.mode_service import ModeService
from app.services.memory_service import MemoryService
from app.services.message_service import MessageService
from app.services.skill_manager import SkillManager
from app.services.skill_service import SkillRegistry
from app.services.stream_events import SseEncoder
from app.services.sync_service import SyncService
from app.services.goal_service import GoalService
from app.services.user_emotion_service import UserEmotionService
from app.services.persona_settings_service import PersonaSettingsService
from app.services.reminder_scheduler_service import ReminderSchedulerService
from app.services.todo_service import TodoService
from app.services.tool_registry import ToolRegistry
from app.services.asr_service import ASRConfig
from app.services.tts_service import TTSConfig
from app.services.voice_service import VoiceService

_bearer = HTTPBearer(auto_error=False)


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
    return ToolRegistry(get_skill_registry(), get_http_client(), session_factory=SessionLocal)


@lru_cache
def get_agent_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(get_agent_service(), get_tool_registry(), get_ai_client())


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService(get_http_client())


@lru_cache
def get_memory_service() -> MemoryService:
    return MemoryService(get_embedding_service(), get_ai_client())


@lru_cache
def get_memory_agent() -> MemoryAgent:
    return MemoryAgent(get_memory_service())


@lru_cache
def get_user_emotion_service() -> UserEmotionService:
    return UserEmotionService()


@lru_cache
def get_agent_coordinator() -> AgentCoordinator:
    return AgentCoordinator(
        RouterAgent(),
        ChatAgent(),
        TaskAgent(get_skill_registry(), get_agent_service(), get_agent_orchestrator()),
        get_memory_agent(),
        get_user_emotion_service(),
    )


@lru_cache
def get_sse_encoder() -> SseEncoder:
    return SseEncoder()


@lru_cache
def get_voice_service() -> VoiceService:
    return VoiceService(
        TTSConfig(
            voice=settings.edge_tts_voice,
            rate=settings.edge_tts_rate,
            volume=settings.edge_tts_volume,
        ),
        ASRConfig(
            engine=settings.asr_engine,
            timeout_seconds=settings.asr_timeout_seconds,
            funasr_api_url=settings.funasr_api_url,
            whisper_api_url=settings.whisper_api_url,
            whisper_api_key=settings.whisper_api_key,
            whisper_fallback_api_key=settings.ai_api_key,
            whisper_base_url=settings.ai_base_url,
            whisper_model=settings.whisper_model,
            whisper_language=settings.whisper_language,
        ),
        get_http_client(),
    )


@lru_cache
def get_live2d_service() -> Live2DService:
    return Live2DService()



def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> UUID:
    if credentials is None:
        from app.core.exceptions import UnauthorizedError

        raise UnauthorizedError("Authentication required")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = UUID(str(payload.get("sub") or ""))
    except (JWTError, ValueError, TypeError) as exc:
        from app.core.exceptions import UnauthorizedError

        raise UnauthorizedError("Invalid access token") from exc
    AuthService(db).get_user_by_id(user_id)
    return user_id


def get_config_service(db: Session = Depends(get_db)) -> ConfigService:
    return ConfigService(db)


def get_skill_manager(db: Session = Depends(get_db)) -> SkillManager:
    return SkillManager(db)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_device_registry_service(db: Session = Depends(get_db)) -> DeviceRegistryService:
    return DeviceRegistryService(db)


def get_character_service() -> CharacterService:
    return CharacterService()


def get_sync_service(db: Session = Depends(get_db)) -> SyncService:
    return SyncService(db)


def get_todo_service(db: Session = Depends(get_db)) -> TodoService:
    return TodoService(db, SyncService(db))


def get_reminder_service(db: Session = Depends(get_db)) -> ReminderSchedulerService:
    from app.services.mode_service import ModeService

    return ReminderSchedulerService(db, mode_service=ModeService(db))


def get_persona_service(db: Session = Depends(get_db)) -> PersonaSettingsService:
    return PersonaSettingsService(db)


def get_goal_service(db: Session = Depends(get_db)) -> GoalService:
    return GoalService(db)


def get_conversation_service(db: Session = Depends(get_db)) -> ConversationService:
    return ConversationService(db)


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(
        db,
        SyncService(db),
        get_agent_orchestrator(),
        ConversationCompactor(),
    )


def get_message_service(db: Session = Depends(get_db)) -> MessageService:
    return MessageService(
        db,
        get_skill_registry(),
        get_agent_service(),
        get_agent_orchestrator(),
        get_ai_client(),
        get_sse_encoder(),
        get_voice_service(),
        get_agent_coordinator(),
        get_memory_agent(),
        ConfigService(db),
        SkillManager(db),
    )


@lru_cache
def get_image_understanding_service() -> ImageUnderstandingService:
    from app.services.vision_client import ConfigurableVisionClient

    return ImageUnderstandingService(ConfigurableVisionClient(get_http_client()))


def get_mode_service(db: Session = Depends(get_db)) -> ModeService:
    return ModeService(db)


def get_diary_service(db: Session = Depends(get_db)) -> DiaryService:
    return DiaryService(db)


def get_live2d_interaction_service(db: Session = Depends(get_db)) -> Live2DInteractionService:
    return Live2DInteractionService(db)


def get_character_profile_service(db: Session = Depends(get_db)) -> CharacterProfileService:
    return CharacterProfileService(db)
