from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AppError,
    BadRequestError,
    ConfigurationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    TooManyRequestsError,
    UnauthorizedError,
    UpstreamServiceError,
)

_STATUS_BY_ERROR_TYPE = {
    BadRequestError: status.HTTP_400_BAD_REQUEST,
    ConfigurationError: status.HTTP_503_SERVICE_UNAVAILABLE,
    ConflictError: status.HTTP_409_CONFLICT,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    PayloadTooLargeError: status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    UnauthorizedError: status.HTTP_401_UNAUTHORIZED,
    TooManyRequestsError: status.HTTP_429_TOO_MANY_REQUESTS,
    UpstreamServiceError: status.HTTP_502_BAD_GATEWAY,
}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    status_code = _STATUS_BY_ERROR_TYPE.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    headers: dict[str, str] = {}
    retry_after = getattr(exc, "retry_after", 0)
    if retry_after > 0:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=status_code, content={"detail": exc.detail}, headers=headers)
