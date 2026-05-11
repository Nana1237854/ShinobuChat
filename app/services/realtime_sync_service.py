import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.models.message import Message
from app.schemas.message import MessageOut


@dataclass(frozen=True)
class SyncSubscription:
    id: str
    user_id: UUID
    device_id: str
    device_type: str
    events: queue.Queue[dict[str, Any]]


@dataclass(frozen=True)
class ApnsTarget:
    user_id: UUID
    device_token: str
    device_name: str
    registered_at: datetime


class RealtimeSyncService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscriptions: dict[str, SyncSubscription] = {}
        self._apns_targets: dict[UUID, dict[str, ApnsTarget]] = {}
        self._apns_outbox: list[dict[str, Any]] = []

    def connect(self, user_id: UUID, device_id: str, device_type: str) -> SyncSubscription:
        subscription = SyncSubscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            device_id=device_id,
            device_type=device_type,
            events=queue.Queue(),
        )
        with self._lock:
            self._subscriptions[subscription.id] = subscription

        subscription.events.put(
            self._event(
                "sync.connected",
                {
                    "connection_id": subscription.id,
                    "user_id": str(user_id),
                    "device_id": device_id,
                    "device_type": device_type,
                    **self.status_payload(user_id),
                },
            )
        )
        self.publish_presence(user_id)
        return subscription

    def disconnect(self, subscription: SyncSubscription) -> None:
        with self._lock:
            self._subscriptions.pop(subscription.id, None)
        self.publish_presence(subscription.user_id)

    def register_apns_target(self, user_id: UUID, device_token: str, device_name: str) -> ApnsTarget:
        target = ApnsTarget(
            user_id=user_id,
            device_token=device_token,
            device_name=device_name,
            registered_at=datetime.utcnow(),
        )
        with self._lock:
            self._apns_targets.setdefault(user_id, {})[device_token] = target
        self.publish_presence(user_id)
        return target

    def publish_message(self, user_id: UUID, message: Message) -> dict[str, Any]:
        delivery = self._ios_delivery_for(user_id)
        payload = {
            "conversation_id": str(message.conversation_id),
            "message": MessageOut.model_validate(message).model_dump(mode="json"),
            "delivery": delivery,
            **self.status_payload(user_id),
        }
        if delivery == "apns_queued":
            self._queue_apns_notification(user_id, payload)
        self.publish(user_id, "message.synced", payload)
        return payload

    def publish_presence(self, user_id: UUID) -> None:
        self.publish(user_id, "presence.changed", self.status_payload(user_id))

    def publish(self, user_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        event = self._event(event_type, payload)
        with self._lock:
            subscribers = [
                item for item in self._subscriptions.values()
                if item.user_id == user_id
            ]
        for subscriber in subscribers:
            subscriber.events.put(event)

    def status_payload(self, user_id: UUID) -> dict[str, Any]:
        with self._lock:
            subscribers = [
                item for item in self._subscriptions.values()
                if item.user_id == user_id
            ]
            online_ios_devices = sum(1 for item in subscribers if item.device_type == "ios")
            ios_push_targets = len(self._apns_targets.get(user_id, {}))
            queued_apns_notifications = sum(1 for item in self._apns_outbox if item["user_id"] == str(user_id))

        return {
            "user_id": str(user_id),
            "online_devices": len(subscribers),
            "online_ios_devices": online_ios_devices,
            "ios_push_targets": ios_push_targets,
            "queued_apns_notifications": queued_apns_notifications,
            "ios_synced": online_ios_devices > 0 or ios_push_targets > 0,
        }

    def format_sse(self, event: dict[str, Any]) -> str:
        return (
            f"event: {event['type']}\n"
            f"data: {json.dumps(event['payload'], ensure_ascii=False)}\n\n"
        )

    def heartbeat_event(self, user_id: UUID) -> dict[str, Any]:
        return self._event(
            "sync.heartbeat",
            {
                "server_time": datetime.utcnow().isoformat(),
                **self.status_payload(user_id),
            },
        )

    def _ios_delivery_for(self, user_id: UUID) -> str:
        status = self.status_payload(user_id)
        if status["online_ios_devices"] > 0:
            return "online"
        if status["ios_push_targets"] > 0:
            return "apns_queued"
        return "no_ios_device"

    def _queue_apns_notification(self, user_id: UUID, payload: dict[str, Any]) -> None:
        if not settings.apns_offline_fallback_enabled:
            return
        with self._lock:
            self._apns_outbox.append(
                {
                    "id": str(uuid.uuid4()),
                    "user_id": str(user_id),
                    "queued_at": datetime.utcnow().isoformat(),
                    "sandbox": settings.apns_sandbox,
                    "payload": payload,
                }
            )

    def _event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "created_at": datetime.utcnow().isoformat(),
            "payload": payload,
        }


realtime_sync_service = RealtimeSyncService()
