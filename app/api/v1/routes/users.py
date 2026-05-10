from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service
from app.schemas.user import UserCreate, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserOut:
    user = auth_service.register_user(payload)
    return UserOut.model_validate(user)
