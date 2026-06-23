class AppError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BadRequestError(AppError):
    pass


class ConfigurationError(AppError):
    pass


class ConflictError(AppError):
    pass


class ForbiddenError(AppError):
    pass


class NotFoundError(AppError):
    pass


class PayloadTooLargeError(AppError):
    pass


class UnauthorizedError(AppError):
    pass


class TooManyRequestsError(AppError):
    def __init__(self, detail: str, retry_after: int = 0):
        super().__init__(detail)
        self.retry_after = retry_after


class UpstreamServiceError(AppError):
    pass
