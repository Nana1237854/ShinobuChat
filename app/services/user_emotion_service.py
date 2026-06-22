from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.schemas.emotion import UserEmotionResult

logger = logging.getLogger(__name__)

# ---- keyword sets ----

_CRISIS_KEYWORDS = [
    "不想活", "想死", "自杀", "自伤", "活不下去", "结束生命", "我想消失",
    "不想活了", "死了算了",
]

_STRESSED_KEYWORDS = [
    "烦死了", "崩溃", "撑不住", "完蛋", "来不及", "压力好大",
    "搞不定", "怎么办", "救命", "焦虑", "烦死了",
    "受不了", "扛不住", "快疯了", "要疯了", "心态崩",
]

_SAD_KEYWORDS = [
    "难过", "伤心", "失望", "不开心", "想哭", "难受", "好想哭",
    "心里难受", "低落",
]

_LONELY_KEYWORDS = [
    "孤独", "睡不着", "没人说话", "好安静", "还没睡",
    "一个人", "好孤单", "没人陪", "寂寞",
]

_TIRED_KEYWORDS = [
    "好累", "疲惫", "没力气", "不想动", "没睡好", "好困",
    "累死了", "筋疲力尽", "浑身没劲",
]

_HAPPY_KEYWORDS = [
    "感谢", "开心", "太好了", "终于好了", "喜欢", "哈哈",
    "ww", "谢谢你", "好棒", "高兴", "太棒了", "开心死了",
    "嘿嘿", "嘻嘻",
]

_FRUSTRATED_KEYWORDS = [
    "又出问题", "怎么回事", "老是", "烦人", "讨厌", "无语",
    "怎么又", "真是的", "气死", "气死了", "好烦",
]

_CONFUSED_KEYWORDS = [
    "不懂", "不明白", "不理解", "什么意思", "搞不懂",
    "搞不明白", "看不懂",
]

_TASK_PATTERNS = [
    "帮我", "查一下", "创建", "打开", "解释", "怎么用",
    "写一个", "帮我查", "帮我写", "帮我改", "看一下",
]

# ---- reply style templates ----

_HINT_TEMPLATES = {
    "stressed": (
        "用户可能有压力或焦虑。回复要短、温柔、先接住情绪，"
        "再给一个很小的下一步。不要长篇说教，不要催促。"
    ),
    "worried": (
        "用户可能有担忧。回复要短、温柔、先接住情绪，"
        "再给一个很小的下一步。不要长篇说教，不要催促。"
    ),
    "tired": (
        "用户可能疲惫。回复要放轻语气，少提要求，多陪伴，"
        "可以温和提醒休息。不要长篇回复。"
    ),
    "lonely": (
        "用户可能感到孤独。回复要放轻语气，少提要求，多陪伴。"
        "不要长篇回复。"
    ),
    "frustrated": (
        "用户可能烦躁。回复要简洁明确，先承认困难，"
        "再给一个可执行解决点，不要反驳用户情绪。"
    ),
    "sad": (
        "用户可能情绪低落。回复要短、温柔、多共情，不提要求。"
        "不要长篇说教。"
    ),
    "confused": (
        "用户可能困惑。回复要清晰简洁，分小步解释，不要一次塞太多信息。"
    ),
    "happy": "用户情绪偏积极。可以更轻松一点回应，但不要夸张。",
    "crisis": (
        "用户可能处于危机状态。优先安全与关怀，"
        "建议联系身边可信的人或当地紧急帮助。"
        "不要独自承担，不要做心理诊断。"
    ),
}


class UserEmotionService:
    def __init__(self, ai_client=None):
        self.ai_client = ai_client

    # ---- public API ----

    def analyze(
        self,
        user_message: str,
        recent_user_messages: list[str] | None = None,
        now: datetime | None = None,
    ) -> UserEmotionResult:
        recent = recent_user_messages or []
        now = now or datetime.now(timezone.utc)

        # 1. Crisis check — always first
        crisis_hit = self._check_crisis(user_message)
        if crisis_hit:
            return UserEmotionResult(
                emotion_label="crisis",
                confidence=1.0,
                intensity=1.0,
                reply_style_hint=_HINT_TEMPLATES["crisis"],
                source="rule",
                should_adjust_reply=True,
            )

        # 2. Score all categories
        combined = " ".join([*recent, user_message])
        scores = {
            "stressed": self._score(combined, _STRESSED_KEYWORDS),
            "sad": self._score(combined, _SAD_KEYWORDS),
            "lonely": self._score(combined, _LONELY_KEYWORDS),
            "tired": self._score(combined, _TIRED_KEYWORDS),
            "happy": self._score(combined, _HAPPY_KEYWORDS),
            "frustrated": self._score(combined, _FRUSTRATED_KEYWORDS),
            "confused": self._score(combined, _CONFUSED_KEYWORDS),
        }

        # 3. Pick top label
        top_label, top_score = max(scores.items(), key=lambda kv: kv[1])

        # 4. Context analysis — consecutive short negatives
        consecutive_neg = self._count_consecutive_negative(recent, user_message)
        context_boost = min(consecutive_neg * 0.15, 0.45)

        # 5. Exclamation boost
        excl_boost = min(user_message.count("!") * 0.06, 0.2)
        if "！" in user_message:
            excl_boost = min(excl_boost + user_message.count("！") * 0.06, 0.2)

        # 6. Time signal (weak)
        time_boost = 0.0
        local_hour = now.hour  # UTC approximation
        if 0 <= local_hour <= 5:
            if scores["lonely"] > 0 or scores["tired"] > 0:
                time_boost = 0.1

        # 7. Intensity
        max_possible = max(
            len(_STRESSED_KEYWORDS), len(_SAD_KEYWORDS), len(_LONELY_KEYWORDS),
            len(_TIRED_KEYWORDS), len(_HAPPY_KEYWORDS), len(_FRUSTRATED_KEYWORDS),
            len(_CONFUSED_KEYWORDS),
        )
        base_intensity = (top_score / max(1, max_possible * 0.15)) * 0.7
        intensity = min(base_intensity + context_boost + excl_boost, 1.0)

        # 8. Confidence
        keyword_density = top_score / max(1, len(user_message) // 10)
        confidence = min(keyword_density * (1.0 + context_boost) + time_boost, 1.0)
        if top_score <= 1 and consecutive_neg == 0:
            confidence = min(confidence, 0.4)

        # 9. Task-detection guard
        is_task = any(p in user_message for p in _TASK_PATTERNS)
        if is_task and confidence < 0.6:
            top_label = "neutral"
            confidence = 0.0
            intensity = 0.0

        # 10. Low confidence fallback
        if top_score == 0 or top_label == "neutral" or confidence < 0.45:
            return UserEmotionResult(
                emotion_label="neutral",
                confidence=round(confidence, 2),
                intensity=round(intensity, 2),
                reply_style_hint="",
                source="rule",
                should_adjust_reply=False,
            )

        # 11. Build result
        hint = _HINT_TEMPLATES.get(top_label, "")

        return UserEmotionResult(
            emotion_label=top_label,
            confidence=round(confidence, 2),
            intensity=round(intensity, 2),
            reply_style_hint=hint,
            source="rule",
            should_adjust_reply=True,
        )

    # ---- private helpers ----

    @staticmethod
    def _check_crisis(text: str) -> bool:
        return any(kw in text for kw in _CRISIS_KEYWORDS)

    @staticmethod
    def _score(text: str, keywords: list[str]) -> int:
        return sum(1 for kw in keywords if kw in text)

    @staticmethod
    def _count_consecutive_negative(recent: list[str], current: str) -> int:
        all_keywords = (
            _STRESSED_KEYWORDS + _SAD_KEYWORDS + _LONELY_KEYWORDS
            + _TIRED_KEYWORDS + _FRUSTRATED_KEYWORDS + _CONFUSED_KEYWORDS
        )

        def _is_negative(msg: str) -> bool:
            return len(msg) < 30 and any(kw in msg for kw in all_keywords)

        count = 1 if _is_negative(current) else 0
        for msg in reversed(recent):
            if _is_negative(msg):
                count += 1
            else:
                break
        return count

    # ---- optional LLM enhancement (inactive by default) ----

    def _llm_analyze(
        self,
        user_message: str,
        recent_user_messages: list[str],
    ) -> dict | None:
        if self.ai_client is None:
            return None
        try:
            recent_text = "\n".join(
                f"- {m[:200]}" for m in recent_user_messages[-5:]
            )
            system_prompt = (
                "你是一个轻量级情绪分析器。分析用户当前消息的情绪状态并返回JSON。"
                "不要输出心理诊断。只输出JSON。"
            )
            user_prompt = (
                f"用户最近消息:\n{recent_text}\n\n"
                f"用户当前消息: {user_message}\n\n"
                '返回JSON格式: {"emotion_label": "...", "confidence": 0.X, '
                '"intensity": 0.X, "reply_style_hint": "...", '
                '"should_adjust_reply": true/false}\n'
                f"emotion_label 必须是以下之一: neutral, happy, worried, "
                f"stressed, tired, lonely, frustrated, sad, confused, crisis\n"
                "如果 confidence < 0.45，should_adjust_reply 为 false，"
                "reply_style_hint 为空字符串。"
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            response = self.ai_client.complete_chat(
                messages, max_tokens=256
            )
            content = response.get("content", "")
            if not content:
                return None
            data = json.loads(content)
            allowed = {
                "neutral", "happy", "worried", "stressed", "tired",
                "lonely", "frustrated", "sad", "confused", "crisis",
            }
            if data.get("emotion_label") not in allowed:
                return None
            return data
        except Exception:
            logger.debug("LLM emotion analysis failed, falling back to rules")
            return None
