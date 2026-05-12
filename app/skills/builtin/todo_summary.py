from uuid import UUID

from pydantic import BaseModel

from app.models.conversation import Conversation
from app.models.message import Message
from app.skills.base import CancelToken, OnProgress, Skill, SkillError, SkillProgress


class TodoSummaryParams(BaseModel):
    user_id: str = ""


class TodoSummarySkill(Skill):
    name = "todo_summary"
    description = "从最近对话中提取待办事项，与已有 Todo 合并去重，输出汇总列表"
    parameters = TodoSummaryParams
    example_triggers = ["整理待办", "我的 todo", "还有什么没做完", "汇总任务", "列出任务"]

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
            raise SkillError("PERMISSION_DENIED", "Missing user_id", "我还不知道要整理谁的待办。")
        try:
            user_uuid = UUID(str(user_id))
        except ValueError as exc:
            raise SkillError("INVALID_PARAMS", str(exc), "用户信息不太对。") from exc

        todo_service = getattr(self, "_todo_service", None)
        if todo_service is None:
            raise SkillError("PERMISSION_DENIED", "TodoService not injected", "待办服务还没接好。")

        await on_progress(SkillProgress(skill_name=self.name, message="扫描最近对话...", percent=0.3))
        db = todo_service.db
        conversation_ids = db.query(Conversation.id).filter(Conversation.user_id == user_uuid)
        recent = (
            db.query(Message)
            .filter(Message.conversation_id.in_(conversation_ids), Message.role == "user")
            .order_by(Message.created_at.desc())
            .limit(30)
            .all()
        )
        if cancel_token.is_set():
            raise SkillError("CANCELLED", "Skill cancelled", "待办整理已取消。")

        await on_progress(SkillProgress(skill_name=self.name, message="合并已有待办...", percent=0.6))
        todos = todo_service.list_by_user(user_uuid, include_completed=True)
        pending = [todo for todo in todos if not todo.completed]
        done = [todo for todo in todos if todo.completed]

        await on_progress(SkillProgress(skill_name=self.name, message="整理输出...", percent=0.9))
        lines = ["# Todo 汇总", "", f"## 待完成（{len(pending)} 项）"]
        for todo in pending:
            mark = "高" if todo.priority >= 4 else "中" if todo.priority == 3 else "低"
            notes = f" - {todo.notes[:60]}" if todo.notes else ""
            lines.append(f"- [{mark}] {todo.title}{notes}")

        if done:
            lines.extend(["", f"## 已完成（{len(done)} 项）"])
            for todo in done[-5:]:
                lines.append(f"- 已完成：{todo.title}")

        lines.append(f"\n> 已扫描最近 {len(recent)} 条消息。新增待办项请直接告诉我。")
        return "\n".join(lines)
