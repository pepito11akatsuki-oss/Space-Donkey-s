from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AgroStakeError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AgroStakeError):
    def __init__(self, message: str = "Recurso no encontrado."):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class ForbiddenError(AgroStakeError):
    def __init__(self, message: str = "No tienes permisos para realizar esta acción."):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class DomainValidationError(AgroStakeError):
    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class ExternalServiceError(AgroStakeError):
    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_502_BAD_GATEWAY)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AgroStakeError)
    async def agrostake_exception_handler(_: Request, exc: AgroStakeError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})