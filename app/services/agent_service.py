from __future__ import annotations

import logging

from app.models.message import Message
from app.services.prefix_cache_manager import PrefixCacheManager
from app.services.skill_service import Skill, SkillRegistry

logger = logging.getLogger("shinobu.agent_service")


class AgentService:
    def __init__(
        self,
        skill_registry: SkillRegistry,
        prefix_cache: PrefixCacheManager | None = None,
    ):
        self.skill_registry = skill_registry
        self.prefix_cache = prefix_cache or PrefixCacheManager()
        self.last_prefix_sha = ""

    def build_messages(
        self,
        content: str,
        history: list[Message],
        activated_skills: list[Skill],
        memory_context: list[str] | None = None,
        user_skills: list[Skill] | None = None,
        tool_catalog: str = "",
    ) -> list[dict]:
        base_system = (
            "你是 ShinobuChat 的 Agent Core，是带有轻量生产力能力的虚拟伴侣，不是编码 Agent。\n"
            "先理解用户意图，再在需要时使用已注册工具。工具没有被注册就不能假设自己拥有它。\n"
            "规则：\n"
            "1. 已激活的 Skill 作为当前任务工作流；需要其他 Skill 时调用 activate_skill。\n"
            "2. 工具结果必须通过机械验证后才能据此声称动作成功。\n"
            "3. 工具结果要解释成自然语言，不要原样倾倒长日志。\n"
            "4. shell_command 仅允许应用注册的只读 curl 策略，不得执行文件或系统修改。\n"
            "5. 缺少真实输入或权限时直接说明，并给安全的下一步。\n"
            "6. 每条最终回复开头使用 [emotion] 标签；可选 happy、sad、angry、surprised、thinking、neutral。"
        )
        skill_catalog = self.skill_registry.render_catalog(user_skills)
        bundle = self.prefix_cache.build(
            base_system=base_system,
            history=history,
            user_message=content,
            skill_catalog=skill_catalog,
            tool_catalog=tool_catalog,
            memory_context=memory_context or [],
            activated_skills=[(skill.name, skill.content) for skill in activated_skills],
            history_limit=16,
        )
        self._track_sha(bundle.pinned_prefix_sha)
        return bundle.messages

    def freeze_agent_prefix(self, tools: list[dict]) -> str:
        base_system = (
            "你是 ShinobuChat 的 Agent Core，是带有轻量生产力能力的虚拟伴侣，不是编码 Agent。\n"
            "先理解用户意图，再在需要时使用已注册工具。工具没有被注册就不能假设自己拥有它。\n"
            "规则：\n"
            "1. 已激活的 Skill 作为当前任务工作流；需要其他 Skill 时调用 activate_skill。\n"
            "2. 工具结果必须通过机械验证后才能据此声称动作成功。\n"
            "3. 工具结果要解释成自然语言，不要原样倾倒长日志。\n"
            "4. shell_command 仅允许应用注册的只读 curl 策略，不得执行文件或系统修改。\n"
            "5. 缺少真实输入或权限时直接说明，并给安全的下一步。\n"
            "6. 每条最终回复开头使用 [emotion] 标签；可选 happy、sad、angry、surprised、thinking、neutral。"
        )
        sha = self.prefix_cache.freeze(base_system, tools, skill_catalog="")
        self.last_prefix_sha = sha
        return sha

    def verify_agent_prefix(self, tools: list[dict]) -> bool:
        base_system = (
            "你是 ShinobuChat 的 Agent Core，是带有轻量生产力能力的虚拟伴侣，不是编码 Agent。\n"
            "先理解用户意图，再在需要时使用已注册工具。工具没有被注册就不能假设自己拥有它。\n"
            "规则：\n"
            "1. 已激活的 Skill 作为当前任务工作流；需要其他 Skill 时调用 activate_skill。\n"
            "2. 工具结果必须通过机械验证后才能据此声称动作成功。\n"
            "3. 工具结果要解释成自然语言，不要原样倾倒长日志。\n"
            "4. shell_command 仅允许应用注册的只读 curl 策略，不得执行文件或系统修改。\n"
            "5. 缺少真实输入或权限时直接说明，并给安全的下一步。\n"
            "6. 每条最终回复开头使用 [emotion] 标签；可选 happy、sad、angry、surprised、thinking、neutral。"
        )
        return self.prefix_cache.verify(base_system, tools)

    def _track_sha(self, sha: str) -> None:
        if sha != self.last_prefix_sha:
            if self.last_prefix_sha:
                logger.info(
                    "Agent prefix SHA changed: old=%s new=%s",
                    self.last_prefix_sha[:16],
                    sha[:16],
                )
            self.last_prefix_sha = sha
