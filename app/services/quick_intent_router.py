"""Quick intent router (F12).

Maps user text → intent_type by keyword / pattern matching.
Does NOT map user text → app_key. That is the user's configuration
responsibility via UserLocalApp.

Only active when route_mode is "auto". Returns a QuickIntentDecision
with confidence >= 0.9 for matches.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from uuid import UUID

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent rules: (label, regex / keyword list, intent_type)
# Each rule produces a confidence score. We require confidence >= 0.9.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _IntentRule:
    intent_type: str
    patterns: list[str]  # regex patterns
    negations: list[str]  # if any negation matches, rule is suppressed
    min_length: int = 2


_RULES: list[_IntentRule] = [
    _IntentRule(
        intent_type="open_music",
        patterns=[
            r"我想听歌",
            r"放.?首.?歌",
            r"放.?点.?音乐",
            r"放音乐",
            r"打开音乐",
            r"播放音乐",
            r"来.?首.?歌",
            r"来点音乐",
            r"听.?歌",
            r"听.?音乐",
            r"放歌",
            r"随便放",
            r"播.?歌",
        ],
        negations=[r"我不想听", r"不听歌", r"不想听歌", r"别放"],
    ),
    _IntentRule(
        intent_type="open_browser",
        patterns=[
            r"打开浏览器",
            r"上网",
            r"浏览网页",
            r"打开网页",
            r"搜一下",
            r"搜索",
        ],
        negations=[r"不要打开浏览器", r"别上网", r"不想搜"],
    ),
    _IntentRule(
        intent_type="open_ide",
        patterns=[
            r"写代码",
            r"打开.?IDE",
            r"打开编辑器",
            r"编程",
            r"打开.?VS",
            r"打开.?VSCode",
            r"打开.?Visual Studio",
            r"打开.?JetBrains",
            r"打开.?PyCharm",
            r"打开.?IntelliJ",
            r"打开.?WebStorm",
            r"开始写代码",
            r"敲代码",
        ],
        negations=[r"不想写", r"不写代码", r"不编程"],
    ),
    _IntentRule(
        intent_type="open_file_explorer",
        patterns=[
            r"打开文件夹",
            r"打开文件管理",
            r"打开资源管理器",
            r"文件管理",
            r"打开目录",
            r"浏览文件",
        ],
        negations=[],
    ),
]

# Complex / long sentence rejection
_COMPLEX_PATTERNS = [
    r"为什么",
    r"怎么(办|样|做|回事)",
    r"如何",
    r"什么是",
    r"告诉我",
    r"解释一下",
    r"说明一下",
    r"(能不能|可以|可以吗|行不行|好吗|对吧|是不是|对不对)\s*[？?]?$",
]


@dataclass(frozen=True)
class QuickIntentDecision:
    matched: bool
    intent_type: str = ""
    confidence: float = 0.0
    label: str = ""
    requires_direct_action: bool = False


class QuickIntentRouter:
    """Match user text to a system intent_type using keyword/pattern rules.

    Only the intent_type is returned — the caller maps intent_type to an
    actual app via LocalAppService.
    """

    def match(
        self,
        user_text: str,
        user_id: UUID,
        conversation_mode: str = "companion",
    ) -> QuickIntentDecision:
        """Return a decision for *user_text*.

        Only returns matched=True when confidence >= 0.9 and the text does
        not look like a complex question or negation.
        """
        text = user_text.strip()
        if not text or len(text) < 2:
            return QuickIntentDecision(matched=False)

        # Reject long / complex sentences
        if len(text) > 50:
            return QuickIntentDecision(matched=False)
        if _matches_complex(text):
            return QuickIntentDecision(matched=False)

        best_intent = ""
        best_confidence = 0.0
        best_label = ""

        for rule in _RULES:
            # Check negations first
            if _any_match(rule.negations, text):
                continue

            # Check positive patterns
            matched_pattern = _first_match(rule.patterns, text)
            if matched_pattern is None:
                continue

            # Compute confidence based on pattern specificity
            pat_len = len(matched_pattern)
            conf = min(0.88 + (pat_len / max(len(text) * 2, 1)), 1.0)

            # Shorter user text with longer pattern → higher confidence
            if len(text) <= 10 and pat_len >= len(text) * 0.6:
                conf = max(conf, 0.95)
            if pat_len >= len(text) * 0.8:
                conf = max(conf, 0.97)

            if conf > best_confidence:
                best_confidence = conf
                best_intent = rule.intent_type
                best_label = matched_pattern

        if best_confidence >= 0.9 and best_intent:
            return QuickIntentDecision(
                matched=True,
                intent_type=best_intent,
                confidence=best_confidence,
                label=best_label,
                requires_direct_action=True,
            )

        return QuickIntentDecision(matched=False)


def _matches_complex(text: str) -> bool:
    """Return True if *text* looks like a complex question, not a simple intent."""
    for pat in _COMPLEX_PATTERNS:
        if re.search(pat, text):
            return True
    return False


def _any_match(patterns: list[str], text: str) -> bool:
    return _first_match(patterns, text) is not None


def _first_match(patterns: list[str], text: str) -> str | None:
    for pat in patterns:
        if re.search(pat, text):
            return pat
    return None
