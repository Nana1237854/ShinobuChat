import re

_SENTENCE_RE = re.compile(r"[。！？!?\.\n](?![」』）\)])")
_COMMA_RE = re.compile(r"[，,](?=\S)")


def split_sentences(text: str) -> tuple[list[str], str]:
    sentences: list[str] = []
    remaining = text
    while remaining:
        match = _SENTENCE_RE.search(remaining)
        if not match:
            break
        end = match.end()
        sentence = remaining[:end].strip()
        if len(sentence) >= 2:
            sentences.append(sentence)
        remaining = remaining[end:]
    return sentences, remaining


def split_long_sentence(text: str, max_len: int = 40) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts = _COMMA_RE.split(text)
    result: list[str] = []
    buf = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        candidate = (buf + "，" + part).strip() if buf else part
        if len(candidate) <= max_len:
            buf = candidate
        else:
            if buf and len(buf) >= 2:
                result.append(buf)
            buf = part
    if buf and len(buf) >= 2:
        result.append(buf)
    return result or [text]
