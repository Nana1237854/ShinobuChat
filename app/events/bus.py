import asyncio

from app.events.types import EventType


class EventBus:
    def __init__(self):
        self._subscriptions: dict[EventType, set[asyncio.Queue]] = {}

    def subscribe(self, event_type: EventType) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscriptions.setdefault(event_type, set()).add(queue)
        return queue

    def unsubscribe(self, event_type: EventType, queue: asyncio.Queue) -> None:
        if event_type in self._subscriptions:
            self._subscriptions[event_type].discard(queue)
            if not self._subscriptions[event_type]:
                del self._subscriptions[event_type]

    async def publish(self, event_type: EventType, payload: dict) -> None:
        for queue in tuple(self._subscriptions.get(event_type, set())):
            await queue.put({"type": event_type, "payload": payload})


bus = EventBus()
