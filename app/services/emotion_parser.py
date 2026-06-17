import re

from app.services.emotion_service import EmotionService

_EMOTION_TAG_RE = re.compile(
    r"^\[\s*(?:emotion\s*[:=]\s*)?(happy|sad|angry|surprised|thinking|neutral)\s*\]",
    re.IGNORECASE,
)
_LEADING_CONTROL_BLOCK_RE = re.compile(
    r"^\s*\[\s*(thinking|thought|analysis)\s*\].*?\[\s*/\s*\1\s*\]\s*",
    re.IGNORECASE | re.DOTALL,
)
_VALID_EMOTIONS = {"happy", "sad", "angry", "surprised", "thinking", "neutral"}


def strip_leading_control_blocks(text: str) -> str:
    cleaned = text
    while True:
        next_cleaned = _LEADING_CONTROL_BLOCK_RE.sub("", cleaned, count=1)
        if next_cleaned == cleaned:
            return cleaned
        cleaned = next_cleaned


def parse_emotion_tag(text: str) -> tuple[str | None, str]:
    stripped = strip_leading_control_blocks(text).strip()
    match = _EMOTION_TAG_RE.match(stripped)
    if match:
        emotion = EmotionService.normalize(match.group(1))
        cleaned = stripped[match.end():].strip()
        return emotion, cleaned
    return None, stripped


def resolve_emotion(parsed_emotion: str | None) -> str:
    normalized = EmotionService.normalize(parsed_emotion)
    if normalized in _VALID_EMOTIONS and parsed_emotion:
        return normalized
    return "neutral"
