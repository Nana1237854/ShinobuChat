import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, UpstreamServiceError
from app.core.time import local_now
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageRole, RouteMode
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.agent_service import AgentService
from app.services.agents import AgentCoordinator, MemoryAgent
from app.services.ai_client import AIClient
from app.services.config_service import ConfigService
from app.services.conversation_service import ConversationService
from app.services.emotion_parser import parse_emotion_tag, resolve_emotion
from app.services.sentence_splitter import split_long_sentence, split_sentences
from app.services.skill_manager import SkillManager
from app.services.skill_service import SkillRegistry
from app.services.stream_events import SseEncoder, StreamEvent
from app.services.text_cleaner import clean_tts_text
from app.services.tts_pipeline import StreamProcessor
from app.services.voice_service import VoiceService


@dataclass
class MessageStreamState:
    conversation: Conversation
    user_message: Message
    route_mode: RouteMode
    router_reason: str
    progress_events: list[StreamEvent]
    reply_text: str
    conversation_mode: str = "companion"


class MessageService:
    def __init__(
        self,
        db: Session,
        skill_registry: SkillRegistry,
        agent: AgentService,
        agent_orchestrator: AgentOrchestrator,
        ai_client: AIClient,
        sse: SseEncoder,
        voice_service: VoiceService | None = None,
        agent_coordinator: AgentCoordinator | None = None,
        memory_agent: MemoryAgent | None = None,
        config_service: ConfigService | None = None,
        skill_manager: SkillManager | None = None,
    ):
        self.db = db
        self.conversations = ConversationService(db)
        self.skill_registry = skill_registry
        self.agent = agent
        self.agent_orchestrator = agent_orchestrator
        self.ai_client = ai_client
        self.sse = sse
        self.voice_service = voice_service
        self.agent_coordinator = agent_coordinator
        self.memory_agent = memory_agent
        self.config_service = config_service
        self.skill_manager = skill_manager

    async def create_streaming_response(self, payload: MessageCreate):
        state, messages = await asyncio.to_thread(self.prepare_stream, payload)
        ai_config = (
            self.config_service.resolve_runtime(payload.user_id)
            if self.config_service is not None
            else None
        )
        max_tokens = int(
            (ai_config or {}).get(
                "ai_lightweight_max_tokens", settings.ai_lightweight_max_tokens
            )
        )

        yield self._format_event(StreamEvent("conversation", {
            "conversation_id": str(state.conversation.id),
            "route_mode": state.route_mode.value,
            "title": state.conversation.title,
            "user_message": self._serialize_message(state.user_message, emotion="neutral"),
        }))

        history = await asyncio.to_thread(
            self.conversations.list_messages, state.conversation.id, payload.user_id
        )

        full_reply = ""
        if state.route_mode is RouteMode.CHAT:
            for chunk in self.ai_client.stream_chat(
                messages, max_tokens=max_tokens, runtime_config=ai_config
            ):
                full_reply += chunk
        else:
            for event in state.progress_events:
                yield self._format_event(event)
            for item in self._run_task_agent(
                messages, history[:-1], payload.user_id, ai_config,
                conversation_mode=state.conversation_mode,
                conversation_id=state.conversation.id,
            ):
                if isinstance(item, StreamEvent):
                    yield self._format_event(item)
                else:
                    full_reply = item

        if not full_reply:
            raise UpstreamServiceError("AI API returned an empty response")

        parsed_emotion, display_text = parse_emotion_tag(full_reply)
        assistant_emotion = resolve_emotion(parsed_emotion)

        state.reply_text = display_text
        yield self._format_event(StreamEvent("emotion", {"emotion": assistant_emotion}))

        tts_full = clean_tts_text(display_text)
        raw_sentences, remaining = split_sentences(tts_full)
        if remaining.strip():
            raw_sentences.append(remaining.strip())

        print(f"[MSG] reply ({len(full_reply)} chars) emotion={assistant_emotion}")
        sentences: list[str] = []
        for sentence in raw_sentences:
            if len(sentence) > 40:
                sentences.extend(split_long_sentence(sentence))
            elif len(sentence) >= 2:
                sentences.append(sentence)
        sentences = [sentence for sentence in sentences if len(sentence) >= 6]
        if sentences:
            print(f"[MSG] {len(sentences)} sentences: {sentences[0][:60]}...")

        if self.voice_service is not None and sentences:
            processor = StreamProcessor(
                voice_service=self.voice_service,
                emotion=assistant_emotion,
                context=[payload.content],
                sse=self.sse,
            )
            for sentence in sentences:
                processor.res_queue.put_nowait(sentence)
            processor.finish_text()

            tts_task = asyncio.create_task(processor.run_tts())
            try:
                while True:
                    item = await processor.audio_queue.get()
                    if item == "__DONE__":
                        break
                    if isinstance(item, dict):
                        yield self._format_event(StreamEvent("audio", item))
            finally:
                processor.cancel()
                await tts_task
        else:
            for sentence in sentences:
                yield self._format_event(StreamEvent("chunk", {"delta": sentence}))

        assistant_messages = await asyncio.to_thread(self.save_sentences, state, sentences)
        yield self._format_event(StreamEvent("done", {
            "conversation_id": str(state.conversation.id),
            "assistant_messages": [
                self._serialize_message(message, emotion=assistant_emotion)
                for message in assistant_messages
            ],
        }))
        self._schedule_memory_write(payload, state)

    def prepare_stream(self, payload: MessageCreate) -> tuple[MessageStreamState, list[dict[str, str]]]:
        user = self.db.query(User).filter(User.id == payload.user_id).first()
        if not user:
            raise NotFoundError("User not found")

        conversation = self._resolve_conversation(payload)
        history = self.conversations.list_messages(conversation.id, payload.user_id)
        agent_plan = self._prepare_agent_plan(payload, history)
        user_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            content=payload.content.strip(),
            route_mode=agent_plan.route_mode.value,
        )
        self.db.add(user_message)
        conversation.updated_at = local_now()
        if conversation.title == "New conversation":
            conversation.title = self._build_title(payload.content)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        self.db.refresh(user_message)

        return MessageStreamState(
            conversation=conversation,
            user_message=user_message,
            route_mode=agent_plan.route_mode,
            router_reason=agent_plan.router_decision.reason,
            progress_events=agent_plan.progress_events,
            reply_text="",
            conversation_mode=agent_plan.conversation_mode,
        ), agent_plan.messages

    def save_sentences(self, state: MessageStreamState, sentences: list[str]) -> list[Message]:
        messages: list[Message] = []
        for sentence_text in sentences:
            message = Message(
                conversation_id=state.conversation.id,
                role=MessageRole.ASSISTANT.value,
                content=sentence_text,
                route_mode=state.route_mode.value,
            )
            self.db.add(message)
            messages.append(message)
        state.conversation.updated_at = local_now()
        state.conversation.summary = self._build_summary(state.reply_text)
        self.db.add(state.conversation)
        self.db.commit()
        for message in messages:
            self.db.refresh(message)
        self.db.refresh(state.conversation)
        return messages

    def _build_ai_messages(self, content: str, route_mode: RouteMode, history: list[Message]) -> list[dict[str, str]]:
        if route_mode is RouteMode.CHAT:
            mode_instruction = "当前是纯聊天模式，优先自然陪伴、澄清想法，用 1-3 句话简短回复。"
        elif route_mode is RouteMode.AGENT:
            mode_instruction = "当前是 Agent 模式，优先把用户意图整理成可执行动作，并明确下一步。"
        else:
            mode_instruction = "当前是自动决策模式，先自然回应，再判断是否需要推进成任务流。"

        messages: list[dict[str, str]] = [{
            "role": MessageRole.SYSTEM.value,
            "content": (
                f"你是 ShinobuChat 的 AI 伙伴。用简洁、温暖、可靠的中文回复用户。{mode_instruction}"
                "\n\n【重要】你的每条回复开头必须包含一个情绪标签，格式为 [emotion]。"
                "可选情绪：happy、sad、angry、surprised、thinking、neutral。"
                "根据你的回复内容选择最匹配的情绪。标签放在回复的最开头，后面接正文。"
                "不要输出 JSON，不要解释标签，不要省略标签。"
                "\n示例：[happy]今天天气真好！\n[sad]抱歉让你失望了..."
            ),
        }]
        for message in history[-12:]:
            if message.role in {MessageRole.USER.value, MessageRole.ASSISTANT.value}:
                messages.append({"role": message.role, "content": message.content})
        messages.append({"role": MessageRole.USER.value, "content": content})
        return messages

    def _prepare_agent_plan(self, payload: MessageCreate, history: list[Message]):
        user_skills = (
            self.skill_manager.runtime_skills(payload.user_id)
            if self.skill_manager is not None
            else []
        )
        if self.agent_coordinator is not None:
            return self.agent_coordinator.prepare(
                requested_route_mode=payload.route_mode,
                user_id=payload.user_id,
                content=payload.content.strip(),
                history=history,
                user_skills=user_skills,
                vision_context=payload.vision_context,
            )

        messages = self._build_ai_messages(payload.content.strip(), payload.route_mode, history)

        return SimpleNamespace(
            route_mode=payload.route_mode,
            router_decision=SimpleNamespace(reason="legacy message service routing"),
            progress_events=[],
            messages=messages,
        )

    def _run_task_agent(
        self,
        messages: list[dict],
        history: list[Message],
        user_id,
        ai_config,
        conversation_mode: str = "companion",
        conversation_id=None,
    ):
        user_skills = (
            self.skill_manager.runtime_skills(user_id)
            if self.skill_manager is not None
            else []
        )
        if self.agent_coordinator is not None:
            yield from self.agent_coordinator.run_task(
                messages,
                history,
                user_skills=user_skills,
                ai_config=ai_config,
                conversation_mode=conversation_mode,
                route_mode="agent",
                user_id=user_id,
                conversation_id=conversation_id,
            )
            return

        activated_skills = self.skill_registry.match(messages[-1].get("content", ""))
        if activated_skills:
            yield StreamEvent("progress", {
                "skill_name": ",".join(skill.name for skill in activated_skills),
                "message": "Loaded SKILL.md",
                "percent": 0.15,
            })
        agent_messages = self.agent.build_messages(
            messages[-1].get("content", ""),
            history,
            activated_skills,
            user_skills=user_skills,
            tool_catalog=self.agent_orchestrator.tool_registry.render_catalog(),
        )
        yield from self.agent_orchestrator.run(
            agent_messages,
            history,
            user_skills=user_skills,
            ai_config=ai_config,
            user_id=user_id,
            conversation_id=conversation_id,
        )

    def _schedule_memory_write(self, payload: MessageCreate, state: MessageStreamState) -> None:
        if self.memory_agent is None:
            return
        asyncio.create_task(
            asyncio.to_thread(
                self.memory_agent.extract_and_store_after_turn,
                user_id=payload.user_id,
                user_text=payload.content,
                assistant_text=state.reply_text,
                source_msg_id=state.user_message.id,
            )
        )

    def _resolve_conversation(self, payload: MessageCreate) -> Conversation:
        if payload.conversation_id:
            return self.conversations.get_for_user(payload.conversation_id, payload.user_id)
        return self.conversations.create_for_user(payload.user_id, title=self._build_title(payload.content))

    def _build_title(self, content: str) -> str:
        flattened = " ".join(content.strip().split())
        return flattened[:36] if flattened else "New conversation"

    def _build_summary(self, content: str) -> str:
        flattened = " ".join(content.strip().split())
        return flattened[:140] if flattened else ""

    def _serialize_message(self, message: Message, emotion: str | None = None) -> dict[str, str]:
        return {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "role": message.role,
            "content": message.content,
            "route_mode": message.route_mode,
            "emotion": emotion,
            "created_at": message.created_at.isoformat(),
        }

    def _format_event(self, event: StreamEvent) -> str:
        return self.sse.encode(event)
