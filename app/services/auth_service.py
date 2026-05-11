from uuid import UUID
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.device import Device
from app.models.user import User
from app.schemas.user import UserCreate


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, payload: UserCreate) -> User:
        existing = self.db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        user = User(
            email=payload.email,
            hashed_password=get_password_hash(payload.password),
            display_name=payload.display_name,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate_user(self, email: str, password: str) -> User:
        user = self.db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        return user

    def get_user_by_id(self, user_id: UUID) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

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

    def _touch_device(self, device_code: str) -> None:
        device = self.db.query(Device).filter(Device.device_code == device_code).first()
        if device:
            device.last_seen_at = datetime.utcnow()
            self.db.add(device)
            self.db.commit()
