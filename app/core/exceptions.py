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


class NotFoundError(AppError):
    pass


class UnauthorizedError(AppError):
    pass


class UpstreamServiceError(AppError):
    pass
