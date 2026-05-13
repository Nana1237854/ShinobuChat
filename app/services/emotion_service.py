from collections.abc import Iterable


class EmotionService:
    POSITIVE = {
        "开心", "高兴", "喜欢", "太好了", "谢谢", "棒", "可爱", "快乐",
        "happy", "glad", "great", "love", "nice", "thanks",
    }
    SAD = {
        "难过", "伤心", "失落", "哭", "孤独", "累", "痛苦", "抱歉",
        "sad", "sorry", "lonely", "tired", "hurt",
    }
    ANGRY = {
        "生气", "愤怒", "讨厌", "烦", "别吵", "气死", "糟糕",
        "angry", "annoyed", "hate", "mad",
    }
    SURPRISED = {
        "惊讶", "真的假的", "没想到", "哇", "竟然", "？", "!",
        "surprise", "wow", "really",
    }
    THINKING = {
        "为什么", "怎么", "如何", "分析", "计划", "方案", "问题", "吗",
        "why", "how", "plan", "think", "analyze",
    }

    @classmethod
    def detect(cls, text: str, context: Iterable[str] | None = None) -> str:
        combined = " ".join([*(context or []), text]).lower()
        scores = {
            "happy": cls._score(combined, cls.POSITIVE),
            "sad": cls._score(combined, cls.SAD),
            "angry": cls._score(combined, cls.ANGRY),
            "surprised": cls._score(combined, cls.SURPRISED),
            "thinking": cls._score(combined, cls.THINKING),
        }
        emotion, score = max(scores.items(), key=lambda item: item[1])
        return emotion if score > 0 else "neutral"

    @staticmethod
    def normalize(emotion: str | None) -> str:
        normalized = (emotion or "neutral").strip().lower().replace(" ", "_")
        return normalized or "neutral"

    @staticmethod
    def _score(text: str, keywords: set[str]) -> int:
        return sum(1 for keyword in keywords if keyword.lower() in text)
