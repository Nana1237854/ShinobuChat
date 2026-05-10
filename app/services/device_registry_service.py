from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.device import Device


class DeviceRegistryService:
    def __init__(self, db: Session):
        self.db = db

    def register_device(self, user_id: UUID, device_code: str, device_name: str, device_type: str) -> Device:
        device = Device(
            user_id=user_id,
            device_code=device_code,
            device_name=device_name,
            device_type=device_type,
            last_seen_at=datetime.utcnow(),
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return device

    def touch_device(self, device_code: str) -> None:
        device = self.db.query(Device).filter(Device.device_code == device_code).first()
        if device:
            device.last_seen_at = datetime.utcnow()
            self.db.add(device)
            self.db.commit()
