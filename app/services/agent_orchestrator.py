from uuid import UUID

from sqlalchemy.orm import Session

from app.models.agent_log import AgentLog
from app.models.message import Message
from app.schemas.agent import AgentResult, Intent, ToolResult
from app.schemas.memory import MemoryCreate
from app.schemas.message import RouteMode
from app.services.intent_recognizer import IntentRecognizer
from app.services.memory_service import MemoryService
from app.services.todo_service import TodoService


class AgentOrchestrator:
    def __init__(self, db: Session, memory_service: MemoryService, todo_service: TodoService):
        self.db = db
        self.memory = memory_service
        self.todo = todo_service
        self.recognizer = IntentRecognizer()

    def execute(
        self,
        user_message: Message,
        history: list[Message],
        user_id: UUID,
        conversation_id: UUID,
        conversation_summary: str = "",
    ) -> AgentResult:
        """Main entry point. Called by ChatService after user message is saved."""
        route_mode = RouteMode(user_message.route_mode) if user_message.route_mode else RouteMode.AUTO

        raw_intents = self.recognizer.classify(user_message.content, route_mode)
        intents = [Intent(**raw_intent) for raw_intent in raw_intents]

        if not intents:
            return AgentResult(
                intents=[],
                tool_results=[],
                reply=self._build_fallback_reply(user_message.content, route_mode, history, conversation_summary),
                route_used="chat",
            )

        tool_results = []
        for intent in intents:
            result = self._dispatch(intent, user_id)
            tool_results.append(result)

        self._write_log(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=user_message.id,
            route_mode=route_mode.value,
            intents=intents,
            tool_results=tool_results,
            input_summary=user_message.content[:200],
        )

        reply = self._build_reply(route_mode, intents, tool_results, history, conversation_summary)
        return AgentResult(
            intents=intents,
            tool_results=tool_results,
            reply=reply,
            route_used=route_mode.value,
        )

    def _dispatch(self, intent: Intent, user_id: UUID) -> ToolResult:
        try:
            if intent.name == "write_memory":
                params = intent.params
                memory = self.memory.create(
                    MemoryCreate(
                        user_id=user_id,
                        title=params.get("title", "Untitled"),
                        content=params.get("content", ""),
                        tags=params.get("tags", []),
                        source="agent",
                        inferred=True,
                        confidence=intent.confidence,
                    )
                )
                return ToolResult(
                    tool="write_memory",
                    status="ok",
                    entity_type="memory",
                    entity_id=memory.id,
                    summary=f"已写入记忆：{memory.title}",
                )

            if intent.name in ("create_todo", "set_reminder"):
                params = intent.params
                todo = self.todo.create(
                    user_id=user_id,
                    title=params.get("title", "Untitled"),
                    priority=params.get("priority", 2),
                    due_at=params.get("due_at"),
                )
                label = "已创建待办" if intent.name == "create_todo" else "已设置提醒"
                due_str = f"，截止 {todo.due_at.isoformat()}" if todo.due_at else ""
                return ToolResult(
                    tool=intent.name,
                    status="ok",
                    entity_type="todo",
                    entity_id=todo.id,
                    summary=f"{label}：{todo.title}{due_str}",
                )

            return ToolResult(
                tool=intent.name,
                status="error",
                entity_type="unknown",
                summary=f"未知意图：{intent.name}",
            )
        except Exception as exc:
            return ToolResult(
                tool=intent.name,
                status="error",
                entity_type="unknown",
                summary=str(exc)[:200],
            )

    def _write_log(
        self,
        user_id: UUID,
        conversation_id: UUID,
        message_id: UUID,
        route_mode: str,
        intents: list[Intent],
        tool_results: list[ToolResult],
        input_summary: str,
    ) -> UUID:
        all_ok = all(result.status == "ok" for result in tool_results)
        log = AgentLog(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            action_type="|".join(result.tool for result in tool_results) or "chat",
            route_mode=route_mode,
            input_summary=input_summary,
            output_summary="; ".join(result.summary for result in tool_results),
            tool_results=[result.model_dump(mode="json") for result in tool_results],
            status="success" if all_ok else ("partial" if tool_results else "failed"),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log.id

    def _build_reply(
        self,
        route_mode: RouteMode,
        intents: list[Intent],
        tool_results: list[ToolResult],
        history: list[Message],
        conversation_summary: str = "",
    ) -> str:
        parts = [result.summary for result in tool_results if result.status == "ok"]
        if not parts:
            return self._build_fallback_reply("", route_mode, history, conversation_summary)
        context = f"（基于之前对话的记忆：{conversation_summary[-200:]}）" if conversation_summary else ""
        return "；".join(parts) + f"。{context}还有什么需要处理的吗？"

    def _build_fallback_reply(
        self,
        content: str,
        route_mode: RouteMode,
        history: list[Message],
        conversation_summary: str = "",
    ) -> str:
        """AUTO mode with no intent recognized -> chat-style reply."""
        focus = content.replace("\r", " ").replace("\n", " ").strip()
        if len(focus) > 80:
            focus = f"{focus[:77]}..."
        prefix = "我没有识别到具体的任务意图，先当作聊天处理。"
        if route_mode == RouteMode.AGENT:
            prefix = "我尝试分析了你的消息，但没有找到可执行的任务。"
        context = f"不过我还记得之前的上下文。{conversation_summary[-200:]}" if conversation_summary else ""
        return f"{prefix}你提到了「{focus}」。{context}需要我帮你梳理一下吗？"
