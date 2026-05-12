from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel

from app.models.conversation import Conversation
from app.models.memory import Memory
from app.models.message import Message
from app.skills.base import CancelToken, OnProgress, Skill, SkillError, SkillProgress


class EveningReviewParams(BaseModel):
    user_id: str = ""
    date: str = ""


class EveningReviewSkill(Skill):
    name = "evening_review"
    description = "复盘一天的聊天内容和关键记忆，生成晚间总结报告"
    parameters = EveningReviewParams
    example_triggers = ["帮我复盘今天", "今天聊了什么", "回顾一下", "晚间复盘", "总结今天"]

    async def execute(
        self,
        params: dict,
        on_progress: OnProgress,
        timeout: float,
        cancel_token: CancelToken,
    ) -> str:
        del timeout
        user_id = params.get("user_id") or ""
        if not user_id:
            raise SkillError("PERMISSION_DENIED", "Missing user_id", "我还不知道要复盘哪个用户。")
        try:
            user_uuid = UUID(str(user_id))
            date_str = params.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
            today = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as exc:
            raise SkillError("INVALID_PARAMS", str(exc), "日期格式不太对，请用 YYYY-MM-DD。") from exc

        memory_service = getattr(self, "_memory_service", None)
        if memory_service is None:
            raise SkillError("PERMISSION_DENIED", "MemoryService not injected", "复盘服务还没接好。")
        db = memory_service.db
        tomorrow = today + timedelta(days=1)

        if cancel_token.is_set():
            raise SkillError("CANCELLED", "Skill cancelled", "复盘已取消。")
        await on_progress(SkillProgress(skill_name=self.name, message="收集今日对话...", percent=0.3))
        conversation_ids = db.query(Conversation.id).filter(Conversation.user_id == user_uuid)
        messages = (
            db.query(Message)
            .filter(
                Message.conversation_id.in_(conversation_ids),
                Message.created_at >= today,
                Message.created_at < tomorrow,
                Message.role == "user",
            )
            .order_by(Message.created_at.asc())
            .limit(50)
            .all()
        )

        if cancel_token.is_set():
            raise SkillError("CANCELLED", "Skill cancelled", "复盘已取消。")
        await on_progress(SkillProgress(skill_name=self.name, message="整理记忆...", percent=0.7))
        memories = (
            db.query(Memory)
            .filter(
                Memory.user_id == user_uuid,
                Memory.updated_at >= today,
                Memory.updated_at < tomorrow,
                Memory.archived.is_(False),
            )
            .order_by(Memory.updated_at.desc())
            .limit(20)
            .all()
        )

        await on_progress(SkillProgress(skill_name=self.name, message="生成报告...", percent=0.95))
        lines = [f"# 复盘报告 - {date_str}", "", f"## 对话摘要（{len(messages)} 条消息）"]
        for message in messages[:15]:
            preview = message.content[:80].replace("\n", " ")
            lines.append(f"- {preview}")

        if memories:
            lines.extend(["", f"## 关键记忆（{len(memories)} 条）"])
            for memory in memories:
                lines.append(f"- [{memory.category}] {memory.title}: {memory.content[:100]}")

        if not messages and not memories:
            lines.append("今天还没有对话或记忆记录。")
        return "\n".join(lines)
