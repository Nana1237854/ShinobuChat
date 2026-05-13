from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, payload: UserCreate) -> User:
        existing = self.db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise ConflictError("Email already registered")

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
            raise UnauthorizedError("Invalid credentials")
        return user

    def get_user_by_id(self, user_id: UUID) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError("User not found")
        return user
