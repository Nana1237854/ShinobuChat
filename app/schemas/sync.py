from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.message import MessageOut


DeviceType = Literal["web", "ios", "unknown"]
SyncDelivery = Literal["online", "apns_queued", "no_ios_device"]
SyncEntityType = Literal["messages", "todos", "memory"]
SyncOperationType = Literal["upsert", "delete"]
SyncResolution = Literal["applied", "ignored", "remote_won", "local_won"]


class SyncConnectQuery(BaseModel):
    user_id: UUID
    device_id: str = Field(min_length=1, max_length=128)
    device_type: DeviceType = "unknown"


class ApnsRegistrationRequest(BaseModel):
    user_id: UUID
    device_token: str = Field(min_length=16, max_length=512)
    device_name: str = Field(default="iPhone", min_length=1, max_length=120)


class ApnsRegistrationResponse(BaseModel):
    user_id: UUID
    device_name: str
    registered_at: datetime
    sandbox: bool


class SyncStatusOut(BaseModel):
    user_id: UUID
    online_devices: int
    online_ios_devices: int
    ios_push_targets: int
    queued_apns_notifications: int
    ios_synced: bool


class SyncMessageEvent(BaseModel):
    conversation_id: UUID
    message: MessageOut
    delivery: SyncDelivery


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    notes: str | None
    completed: bool
    priority: int
    due_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SyncChangeIn(BaseModel):
    entity_type: SyncEntityType
    entity_id: UUID
    operation: SyncOperationType = "upsert"
    data: dict[str, Any] = Field(default_factory=dict)
    vector_clock: dict[str, int] = Field(default_factory=dict)
    updated_at: datetime
    client_change_id: str | None = Field(default=None, max_length=128)


class SyncPushRequest(BaseModel):
    user_id: UUID
    device_id: str = Field(min_length=1, max_length=128)
    last_seen_version: int = Field(default=0, ge=0)
    changes: list[SyncChangeIn] = Field(default_factory=list, max_length=200)


class SyncChangeOut(BaseModel):
    entity_type: SyncEntityType
    entity_id: UUID
    operation: SyncOperationType
    data: dict[str, Any]
    vector_clock: dict[str, int]
    server_version: int
    updated_at: datetime
    deleted: bool = False


class SyncPushResult(BaseModel):
    client_change_id: str | None
    entity_type: SyncEntityType
    entity_id: UUID
    operation: SyncOperationType
    resolution: SyncResolution
    server_version: int
    vector_clock: dict[str, int]
    conflict: bool = False
    remote: SyncChangeOut | None = None


class SyncPushResponse(BaseModel):
    user_id: UUID
    device_id: str
    server_version: int
    next_since_version: int
    results: list[SyncPushResult]
    changes: list[SyncChangeOut]


class SyncPullResponse(BaseModel):
    user_id: UUID
    server_version: int
    next_since_version: int
    changes: list[SyncChangeOut]
