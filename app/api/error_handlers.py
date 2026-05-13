from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AppError,
    BadRequestError,
    ConfigurationError,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    UpstreamServiceError,
)

_STATUS_BY_ERROR_TYPE = {
    BadRequestError: status.HTTP_400_BAD_REQUEST,
    ConfigurationError: status.HTTP_503_SERVICE_UNAVAILABLE,
    ConflictError: status.HTTP_409_CONFLICT,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    UnauthorizedError: status.HTTP_401_UNAUTHORIZED,
    UpstreamServiceError: status.HTTP_502_BAD_GATEWAY,
}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    status_code = _STATUS_BY_ERROR_TYPE.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    return JSONResponse(status_code=status_code, content={"detail": exc.detail})
