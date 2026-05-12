from collections import defaultdict
from uuid import UUID

from pydantic import BaseModel

from app.schemas.memory import MemoryCategory
from app.skills.base import CancelToken, OnProgress, Skill, SkillError, SkillProgress


class InspirationOrganizerParams(BaseModel):
    user_id: str = ""
    query: str = ""


class InspirationOrganizerSkill(Skill):
    name = "inspiration_organizer"
    description = "整理灵感笔记，按标签聚类展示，帮助用户回顾和连接想法"
    parameters = InspirationOrganizerParams
    example_triggers = ["整理灵感", "最近有什么想法", "我的灵感笔记", "回顾灵感", "整理思路", "看看我的想法"]

    async def execute(
        self,
        params: dict,
        on_progress: OnProgress,
        timeout: float,
        cancel_token: CancelToken,
    ) -> str:
        del timeout
        user_id = params.get("user_id") or ""
        query = str(params.get("query") or "").strip().lower()
        if not user_id:
            raise SkillError("PERMISSION_DENIED", "Missing user_id", "我还不知道要整理谁的灵感。")
        try:
            user_uuid = UUID(str(user_id))
        except ValueError as exc:
            raise SkillError("INVALID_PARAMS", str(exc), "用户信息不太对。") from exc

        memory_service = getattr(self, "_memory_service", None)
        if memory_service is None:
            raise SkillError("PERMISSION_DENIED", "MemoryService not injected", "记忆服务还没接好。")

        await on_progress(SkillProgress(skill_name=self.name, message="检索灵感记录...", percent=0.4))
        memories = memory_service.list_by_user(user_uuid, MemoryCategory.INSPIRATION)
        if query:
            memories = [
                memory
                for memory in memories
                if query in memory.title.lower() or query in memory.content.lower()
            ]
        if cancel_token.is_set():
            raise SkillError("CANCELLED", "Skill cancelled", "灵感整理已取消。")

        await on_progress(SkillProgress(skill_name=self.name, message="聚类整理...", percent=0.85))
        tag_groups: dict[str, list] = defaultdict(list)
        untagged = []
        for memory in memories:
            if memory.tags:
                for tag in memory.tags:
                    tag_groups[tag].append(memory)
            else:
                untagged.append(memory)

        lines = ["# 灵感整理"]
        if not memories:
            lines.append("还没有灵感记录。想到什么随时告诉我，我帮你记下来。")
            return "\n".join(lines)

        for tag, items in sorted(tag_groups.items(), key=lambda item: -len(item[1])):
            lines.extend(["", f"## {tag}（{len(items)} 条）"])
            for memory in items[:5]:
                lines.append(f"- {memory.title}: {memory.content[:120]}")

        if untagged:
            lines.extend(["", f"## 未分类（{len(untagged)} 条）"])
            for memory in untagged[:5]:
                lines.append(f"- {memory.title}: {memory.content[:120]}")

        lines.append(f"\n> 共 {len(memories)} 条灵感记录")
        return "\n".join(lines)
