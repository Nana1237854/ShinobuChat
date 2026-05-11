from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.message import MessageOut


DeviceType = Literal["web", "ios", "unknown"]
SyncDelivery = Literal["online", "apns_queued", "no_ios_device"]


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
