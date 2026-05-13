import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib import error, request

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageRole, RouteMode
from app.services.agent_service import AgentService
from app.services.conversation_service import ConversationService
from app.services.skill_service import SkillRegistry

_SKILL_REGISTRY = SkillRegistry(Path(__file__).resolve().parents[2] / "skills")
_AGENT_SERVICE = AgentService(_SKILL_REGISTRY)


@dataclass
class MessageStreamState:
    conversation: Conversation
    user_message: Message
    route_mode: RouteMode
    reply_text: str


class MessageService:
    def __init__(self, db: Session):
        self.db = db
        self.conversations = ConversationService(db)
        self.skill_registry = _SKILL_REGISTRY
        self.agent = _AGENT_SERVICE

    def prepare_stream(self, payload: MessageCreate) -> tuple[MessageStreamState, list[dict[str, str]]]:
        user = self.db.query(User).filter(User.id == payload.user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        conversation = self._resolve_conversation(payload)
        user_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            content=payload.content.strip(),
            route_mode=payload.route_mode.value,
        )
        self.db.add(user_message)
        conversation.updated_at = datetime.utcnow()
        if conversation.title == "New conversation":
            conversation.title = self._build_title(payload.content)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        self.db.refresh(user_message)

        history = self.conversations.list_messages(conversation.id, payload.user_id)
        messages = self._build_ai_messages(payload.content.strip(), payload.route_mode, history[:-1])

        state = MessageStreamState(
            conversation=conversation,
            user_message=user_message,
            route_mode=payload.route_mode,
            reply_text="",
        )
        return state, messages

    def save_assistant_message(self, state: MessageStreamState) -> Message:
        assistant_message = Message(
            conversation_id=state.conversation.id,
            role=MessageRole.ASSISTANT.value,
            content=state.reply_text,
            route_mode=state.route_mode.value,
        )
        state.conversation.updated_at = datetime.utcnow()
        state.conversation.summary = self._build_summary(state.reply_text)
        self.db.add(assistant_message)
        self.db.add(state.conversation)
        self.db.commit()
        self.db.refresh(state.conversation)
        self.db.refresh(assistant_message)
        return assistant_message

    def create_streaming_response(self, payload: MessageCreate):
        state, messages = self.prepare_stream(payload)
        max_tokens = settings.ai_lightweight_max_tokens

        def event_stream():
            yield self._format_event(
                "conversation",
                {
                    "conversation_id": str(state.conversation.id),
                    "route_mode": state.route_mode.value,
                    "title": state.conversation.title,
                    "user_message": self._serialize_message(state.user_message),
                },
            )

            history = self.conversations.list_messages(state.conversation.id, payload.user_id)
            full_reply = ""
            if state.route_mode is RouteMode.CHAT:
                for chunk in self._call_ai_stream(messages, max_tokens=max_tokens):
                    full_reply += chunk
                    yield self._format_event("chunk", {"delta": chunk})
            else:
                activated_skills = self.skill_registry.match(payload.content)
                if activated_skills:
                    yield self._format_event(
                        "progress",
                        {
                            "skill_name": ",".join(skill.name for skill in activated_skills),
                            "message": "Loaded SKILL.md",
                            "percent": 0.15,
                        },
                    )
                agent_messages = self.agent.build_messages(payload.content.strip(), history[:-1], activated_skills)
                full_reply = yield from self._run_agent(agent_messages, history[:-1])

            if not full_reply:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="AI API returned an empty response",
                )

            state.reply_text = full_reply
            assistant_message = self.save_assistant_message(state)
            yield self._format_event(
                "done",
                {
                    "conversation_id": str(state.conversation.id),
                    "assistant_message": self._serialize_message(assistant_message),
                },
            )

        return event_stream()

    def _run_agent(self, messages: list[dict], history: list[Message]):
        tools = self.agent.tools()
        for step in range(max(settings.agent_max_steps, 1)):
            yield self._format_event(
                "progress",
                {
                    "skill_name": "agent",
                    "message": f"Thinking step {step + 1}",
                    "percent": min(0.25 + step * 0.1, 0.85),
                },
            )
            assistant_message = self._call_ai_completion(
                messages,
                tools=tools,
                max_tokens=settings.ai_lightweight_max_tokens,
            )
            tool_calls = assistant_message.get("tool_calls") or []
            content = assistant_message.get("content") or ""
            if not tool_calls:
                if content:
                    yield self._format_event("chunk", {"delta": content})
                return content

            messages.append(assistant_message)
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name = function.get("name", "unknown")
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                yield self._format_event(
                    "progress",
                    {
                        "skill_name": tool_name,
                        "message": "Running tool",
                        "percent": min(0.35 + step * 0.1, 0.9),
                    },
                )
                result = self.agent.execute_tool(tool_name, arguments, history)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "content": result,
                    }
                )

        fallback = "任务步骤已达到上限。我已经停止继续调用工具，请把需求拆小一点或补充更明确的目标。"
        yield self._format_event("chunk", {"delta": fallback})
        return fallback

    def _build_ai_messages(
        self,
        content: str,
        route_mode: RouteMode,
        history: list[Message],
    ) -> list[dict[str, str]]:
        if route_mode is RouteMode.CHAT:
            mode_instruction = "当前是纯聊天模式，优先自然陪伴、澄清想法，用 1-3 句话简短回复。"
        elif route_mode is RouteMode.AGENT:
            mode_instruction = "当前是 Agent 模式，优先把用户意图整理成可执行动作，并明确下一步。"
        else:
            mode_instruction = "当前是自动决策模式，先自然回应，再判断是否需要推进成任务流。"

        messages: list[dict[str, str]] = [
            {
                "role": MessageRole.SYSTEM.value,
                "content": (
                    "你是 ShinobuChat 的 AI 伙伴。用简洁、温暖、可靠的中文回复用户。"
                    f"{mode_instruction}"
                ),
            }
        ]
        for message in history[-12:]:
            if message.role in {MessageRole.USER.value, MessageRole.ASSISTANT.value}:
                messages.append({"role": message.role, "content": message.content})
        messages.append({"role": MessageRole.USER.value, "content": content})
        return messages

    def _call_ai_stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
    ):
        if not settings.ai_api_key or settings.ai_api_key == "your-api-key":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI API key is not configured",
            )

        body: dict = {
            "model": settings.ai_model,
            "messages": messages,
            "temperature": 0.7,
            "stream": True,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens

        endpoint = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
        req = request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.ai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            resp = request.urlopen(req, timeout=settings.ai_request_timeout_seconds)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI API request failed: {detail}",
            ) from exc
        except (error.URLError, TimeoutError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI API request failed: {exc}",
            ) from exc

        buffer = b""
        try:
            while True:
                data = resp.read(4096)
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line or line == b"data: [DONE]":
                        continue
                    if line.startswith(b"data: "):
                        try:
                            chunk_data = json.loads(line[6:])
                            delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                yield token
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI stream failed: {exc}",
            ) from exc

    def _call_ai_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        if not settings.ai_api_key or settings.ai_api_key == "your-api-key":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI API key is not configured",
            )

        body: dict = {
            "model": settings.ai_model,
            "messages": messages,
            "temperature": 0.4,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if max_tokens:
            body["max_tokens"] = max_tokens

        endpoint = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
        req = request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.ai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=settings.ai_request_timeout_seconds) as resp:
                response_data = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI API request failed: {detail}",
            ) from exc
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI API request failed: {exc}",
            ) from exc

        try:
            return response_data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI API returned an invalid completion response",
            ) from exc

    def _resolve_conversation(self, payload: MessageCreate) -> Conversation:
        if payload.conversation_id:
            return self.conversations.get_for_user(payload.conversation_id, payload.user_id)
        return self.conversations.create_for_user(
            payload.user_id,
            title=self._build_title(payload.content),
        )

    def _build_title(self, content: str) -> str:
        flattened = " ".join(content.strip().split())
        if not flattened:
            return "New conversation"
        return flattened[:36]

    def _build_summary(self, content: str) -> str:
        flattened = " ".join(content.strip().split())
        return flattened[:140] if flattened else ""

    def _serialize_message(self, message: Message) -> dict[str, str]:
        return {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "role": message.role,
            "content": message.content,
            "route_mode": message.route_mode,
            "created_at": message.created_at.isoformat(),
        }

    def _format_event(self, event: str, payload: dict[str, object]) -> str:
        data = json.dumps(payload, ensure_ascii=False)
        return f"event: {event}\ndata: {data}\n\n"
