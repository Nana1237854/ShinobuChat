import re
import unicodedata

_TTS_PUNCTUATION_RE = re.compile(r"[。！？!?，,、；;：:…～~\.\-\—\(\)（）\[\]【】「」『』“”\"'`]")


def clean_tts_text(text: str) -> str:
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    cleaned = re.sub(r"\*(.+?)\*", r"\1", cleaned)
    cleaned = re.sub(r"__(.+?)__", r"\1", cleaned)
    cleaned = re.sub(r"_(.+?)_", r"\1", cleaned)
    cleaned = re.sub(r"~~(.+?)~~", r"\1", cleaned)
    cleaned = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", cleaned)
    cleaned = re.sub(r"(?<!\w)\*\*(?!\w)", "", cleaned)
    cleaned = re.sub(r"(?<!\w)__(?!\w)", "", cleaned)
    cleaned = re.sub(r"(?<!\w)~~(?!\w)", "", cleaned)
    cleaned = re.sub(r"(?m)^#{1,6}\s+", "", cleaned)
    cleaned = re.sub(r"(?m)^[-*+]\s+", "", cleaned)
    cleaned = re.sub(r"(?m)^\d+[\.\)]\s*", "", cleaned)
    cleaned = re.sub(r"(?m)^\|?[-:| ]+\|[-:| ]+\|?$", "", cleaned)
    cleaned = re.sub(r"(?m)^\|.+\|$", "", cleaned)
    cleaned = re.sub(r"\|", " ", cleaned)
    cleaned = re.sub(r"\s*[→➡]\s*", " ", cleaned)
    cleaned = re.sub(r"^[。！？，、；：…～\.\!\?,;:\s\*\-—]+", "", cleaned)
    cleaned = re.sub(r"[，、；：…～,;:\s\*\-—]+$", "", cleaned)
    cleaned = re.sub(r"[。！？!?\.]{2,}", lambda m: m.group()[0], cleaned)
    cleaned = "".join(ch for ch in cleaned if unicodedata.category(ch) not in ("So", "Sk", "Cn"))
    cleaned = re.sub(r"^[。！？，、；：…～\.\!\?,;:\s\*\-—]+", "", cleaned)
    cleaned = re.sub(r"[，、；：…～,;:\s\*\-—]+$", "", cleaned)
    cleaned = cleaned.replace(" ", "").replace("\n", "").replace("\r", "")
    return cleaned.strip()


def strip_tts_punctuation(text: str) -> str:
    return _TTS_PUNCTUATION_RE.sub("", text).strip()
