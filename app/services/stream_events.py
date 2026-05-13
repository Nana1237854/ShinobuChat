from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class StreamEvent:
    event: str
    payload: dict[str, object]


class SseEncoder:
    def encode(self, event: StreamEvent) -> str:
        data = json.dumps(event.payload, ensure_ascii=False)
        return f"event: {event.event}\ndata: {data}\n\n"
