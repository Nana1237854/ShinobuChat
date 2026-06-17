from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.message import RouteMode


@dataclass(frozen=True)
class RouterDecision:
    target: RouteMode
    confidence: float
    reason: str


class RouterAgent:
    _task_patterns = [
        r"https?://",
        r"\bwww\.",
        r"天气",
        r"查询",
        r"搜索",
        r"网页",
        r"抓取",
        r"总结",
        r"整理",
        r"执行",
        r"运行",
        r"帮我做",
        r"生成报告",
        r"列出",
        r"对比",
        r"翻译",
        r"计算",
        r"todo",
        r"提醒",
        r"agent",
        r"tool",
        r"curl",
    ]

    def route(self, content: str) -> RouterDecision:
        text = content.strip().lower()
        if not text:
            return RouterDecision(RouteMode.CHAT, 0.55, "empty message defaults to chat")

        for pattern in self._task_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return RouterDecision(RouteMode.AGENT, 0.86, f"matched task pattern: {pattern}")

        if len(text) > 160 and any(token in text for token in ("请", "帮", "需要", "如何")):
            return RouterDecision(RouteMode.AGENT, 0.72, "long instruction-like message")

        return RouterDecision(RouteMode.CHAT, 0.82, "no task pattern matched")
