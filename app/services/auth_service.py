from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db_utils import require_user
from app.core.exceptions import ConflictError
from app.models.device import Device
from app.models.user import User
from app.schemas.user import UserCreate

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, payload: UserCreate) -> User:
        existing = self.db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise ConflictError("Email already registered")

        user = User(
            email=payload.email,
            hashed_password=self._hash_password(payload.password),
            display_name=payload.display_name,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate_user(self, email: str, password: str) -> User:
        user = self.db.query(User).filter(User.email == email).first()
        if not user or not self._verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        return user

    def get_user_by_id(self, user_id: UUID) -> User:
        require_user(self.db, user_id)
        return self.db.query(User).filter(User.id == user_id).first()

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

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def _hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def create_access_token(self, subject: str, expires_minutes: int | None = None) -> str:
        minutes = expires_minutes or settings.jwt_access_token_expire_minutes
        expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        payload = {"sub": subject, "exp": expire}
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
