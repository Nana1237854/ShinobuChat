import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_auth_service
from app.core.config import settings
from app.schemas.auth import (
    DeviceAuthorizeRequest,
    DeviceAuthorizeResponse,
    DeviceTokenRequest,
    DeviceTokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

# MVP in-memory state for pending device authorizations.
PENDING_DEVICE_AUTH: dict[str, dict] = {}


@router.post("/device/authorize", response_model=DeviceAuthorizeResponse)
def authorize_device(
    payload: DeviceAuthorizeRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> DeviceAuthorizeResponse:
    user = auth_service.authenticate_user(payload.email, payload.password)

    device_code = secrets.token_urlsafe(32)
    user_code = secrets.token_hex(4).upper()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.oauth2_device_code_ttl_seconds)

    PENDING_DEVICE_AUTH[device_code] = {
        "user_id": str(user.id),
        "device_name": payload.device_name,
        "device_type": payload.device_type,
        "approved": True,
        "expires_at": expires_at,
    }

    return DeviceAuthorizeResponse(
        device_code=device_code,
        user_code=user_code,
        verification_uri="/api/v1/auth/device/authorize",
        expires_in=settings.oauth2_device_code_ttl_seconds,
        interval=settings.oauth2_poll_interval_seconds,
    )


@router.post("/device/token", response_model=DeviceTokenResponse)
def device_token(
    payload: DeviceTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> DeviceTokenResponse:
    auth_record = PENDING_DEVICE_AUTH.get(payload.device_code)
    if not auth_record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_device_code")

    if datetime.now(timezone.utc) > auth_record["expires_at"]:
        PENDING_DEVICE_AUTH.pop(payload.device_code, None)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="expired_token")

    if not auth_record["approved"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="authorization_pending")

    auth_service.register_device(
        user_id=UUID(auth_record["user_id"]),
        device_code=payload.device_code,
        device_name=auth_record["device_name"],
        device_type=auth_record["device_type"],
    )

    access_token = auth_service.create_access_token(subject=auth_record["user_id"])
    PENDING_DEVICE_AUTH.pop(payload.device_code, None)

    return DeviceTokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )
