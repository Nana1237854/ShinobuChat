import re
from datetime import datetime, timedelta

from app.schemas.message import RouteMode


INTENT_PATTERNS = [
    {
        "name": "write_memory",
        "keywords": ["记住", "备忘", "保存", "记录", "写入记忆", "记一下", "记下来", "存一下", "存档"],
        "extract": "_extract_memory_params",
    },
    {
        "name": "set_reminder",
        "keywords": ["提醒", "几点", "明天", "后天", "日期", "截止", "ddl", "之前", "到期"],
        "extract": "_extract_reminder_params",
    },
    {
        "name": "create_todo",
        "keywords": ["待办", "任务", "todo", "要做", "需要做", "还得", "还没", "别忘了"],
        "extract": "_extract_todo_params",
    },
]


class IntentRecognizer:
    def classify(self, content: str, route_mode: RouteMode) -> list[dict]:
        """
        Return list of intents: [{name, params, confidence}, ...].
        In AUTO mode: recognize first, fallback to empty list (-> chat).
        In AGENT mode: force recognize at least one intent.
        In CHAT mode: return empty list (skip agent entirely).
        """
        if route_mode == RouteMode.CHAT:
            return []

        intents = []
        for pattern in INTENT_PATTERNS:
            if self._match_keywords(content, pattern["keywords"]):
                extractor = getattr(self, pattern["extract"])
                params = extractor(content)
                intents.append(
                    {
                        "name": pattern["name"],
                        "params": params,
                        "confidence": self._keyword_confidence(content, pattern["keywords"]),
                    }
                )

        if route_mode == RouteMode.AGENT and not intents:
            intents.append(
                {
                    "name": "write_memory",
                    "params": self._extract_memory_params(content),
                    "confidence": 0.5,
                }
            )

        return intents

    def _match_keywords(self, content: str, keywords: list[str]) -> bool:
        return any(keyword in content for keyword in keywords)

    def _keyword_confidence(self, content: str, keywords: list[str]) -> float:
        hits = sum(1 for keyword in keywords if keyword in content)
        return min(1.0, hits / max(len(keywords), 1) + 0.3)

    def _extract_memory_params(self, content: str) -> dict:
        cleaned = content.strip()
        title = cleaned[:36] if len(cleaned) > 36 else cleaned
        tags = self._extract_tags(cleaned)
        return {"title": title, "content": cleaned, "tags": tags}

    def _extract_todo_params(self, content: str) -> dict:
        title = content.strip()
        for keyword in ["待办", "任务", "todo", "要做", "需要做", "还得", "还没", "别忘了"]:
            title = title.replace(keyword, "").strip()
        if not title:
            title = content.strip()[:60]

        priority = 3
        if "紧急" in content or "马上" in content or "立刻" in content:
            priority = 5
        elif "重要" in content:
            priority = 4

        return {"title": title[:120], "priority": priority}

    def _extract_reminder_params(self, content: str) -> dict:
        title = content.strip()
        for keyword in ["提醒", "一下", "我"]:
            title = title.replace(keyword, "").strip()
        due_at = self._parse_cn_datetime(content)
        return {"title": title[:120], "due_at": due_at}

    def _extract_tags(self, content: str) -> list[str]:
        hashtags = re.findall(r"#(\S{1,30})", content)
        return hashtags[:12]

    _WEEKDAY_MAP = {
        "周一": 0,
        "周二": 1,
        "周三": 2,
        "周四": 3,
        "周五": 4,
        "周六": 5,
        "周日": 6,
        "星期一": 0,
        "星期二": 1,
        "星期三": 2,
        "星期四": 3,
        "星期五": 4,
        "星期六": 5,
        "星期天": 6,
    }
    _HOUR_RE = re.compile(r"(\d{1,2})\s*[点:：]\s*(\d{0,2})?\s*(分)?")

    def _parse_cn_datetime(self, text: str) -> datetime | None:
        now = datetime.now()
        target_date = now.date()
        hour, minute = 23, 59
        has_date = False
        has_time = False

        if "明天" in text:
            target_date = now.date() + timedelta(days=1)
            has_date = True
        elif "后天" in text:
            target_date = now.date() + timedelta(days=2)
            has_date = True
        elif "今天" in text:
            target_date = now.date()
            has_date = True

        for cn_name, weekday in self._WEEKDAY_MAP.items():
            if cn_name in text:
                days_ahead = weekday - now.weekday()
                if "下" in text and cn_name in text[text.index("下") :]:
                    days_ahead += 7
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = now.date() + timedelta(days=days_ahead)
                has_date = True
                break

        time_match = self._HOUR_RE.search(text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            if "下午" in text and hour < 12:
                hour += 12
            if "上午" in text and hour == 12:
                hour = 0
            has_time = True

        if not has_date and not has_time:
            return None

        return datetime(target_date.year, target_date.month, target_date.day, hour, minute, 0)
