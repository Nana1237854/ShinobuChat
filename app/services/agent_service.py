from __future__ import annotations

from app.models.message import Message
from app.schemas.message import MessageRole
from app.services.skill_service import Skill, SkillRegistry


class AgentService:
    def __init__(self, skill_registry: SkillRegistry):
        self.skill_registry = skill_registry

    def build_messages(
        self,
        content: str,
        history: list[Message],
        activated_skills: list[Skill],
        memory_context: list[str] | None = None,
    ) -> list[dict]:
        skill_blocks = "\n\n".join(
            f"<skill name=\"{skill.name}\">\n{skill.content}\n</skill>"
            for skill in activated_skills
        )
        system = (
            "你是 ShinobuChat 的 Agent Core。你不只是在聊天，也会在需要时使用工具完成任务。\n"
            "技能系统遵循 AgentSkills/EchoBot 风格：先激活匹配的 SKILL.md，把其中工作流当作当前任务说明，"
            "再调用通用工具获取事实或执行只读动作，最后用中文给用户一个清楚、简短、可用的结果。\n\n"
            "可用技能目录：\n"
            f"{self.skill_registry.render_catalog() or '- 当前没有安装技能'}\n\n"
            "规则：\n"
            "1. 已注入的技能优先执行；需要其他技能时调用 activate_skill。\n"
            "2. 工具结果要被你解释成自然语言，不要原样倾倒长日志。\n"
            "3. shell_command 只用于 SKILL.md 明确要求的只读 curl 请求。\n"
            "4. 如果技能需要当前后端拿不到的输入，例如真实屏幕截图，先说明缺少什么，再给下一步。\n"
        )
        if memory_context:
            memory_items = "\n".join(f"- {item}" for item in memory_context)
            system += f"\n长期记忆上下文：\n{memory_items}\n请在任务回复中自然参考这些记忆，不要生硬复述。\n"
        if skill_blocks:
            system += f"\n已激活技能：\n{skill_blocks}\n"

        messages: list[dict] = [{"role": MessageRole.SYSTEM.value, "content": system}]
        for message in history[-16:]:
            if message.role in {MessageRole.USER.value, MessageRole.ASSISTANT.value}:
                messages.append({"role": message.role, "content": message.content})
        messages.append({"role": MessageRole.USER.value, "content": content})
        return messages
