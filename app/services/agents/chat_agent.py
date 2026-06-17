from __future__ import annotations

from app.models.message import Message
from app.schemas.message import MessageRole


class ChatAgent:
    def build_messages(
        self,
        content: str,
        history: list[Message],
        memory_context: list[str] | None = None,
    ) -> list[dict[str, str]]:
        memory_block = self._format_memory_context(memory_context or [])
        system = (
            "你是 ShinobuChat 的 AI 伙伴。用简洁、温暖、可靠的中文回复用户。"
            "当前是纯聊天模式，优先自然陪伴、澄清想法，用 1-3 句话简短回复。"
            "\n\n【重要】你的每条回复开头必须包含一个情绪标签，格式为 [emotion]。"
            "可选情绪：happy、sad、angry、surprised、thinking、neutral。"
            "根据你的回复内容选择最匹配的情绪。标签放在回复的最开头，后面接正文。"
            "不要输出 JSON，不要解释标签，不要省略标签。"
            "\n示例：[happy]今天天气真好！\n[sad]抱歉让你失望了..."
        )
        if memory_block:
            system += f"\n\n{memory_block}"

        messages: list[dict[str, str]] = [{"role": MessageRole.SYSTEM.value, "content": system}]
        for message in history[-12:]:
            if message.role in {MessageRole.USER.value, MessageRole.ASSISTANT.value}:
                messages.append({"role": message.role, "content": message.content})
        messages.append({"role": MessageRole.USER.value, "content": content})
        return messages

    def _format_memory_context(self, memories: list[str]) -> str:
        if not memories:
            return ""
        items = "\n".join(f"- {memory}" for memory in memories)
        return f"【长期记忆上下文】\n{items}\n请自然参考这些记忆，不要生硬复述。"
