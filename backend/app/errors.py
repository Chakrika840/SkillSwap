"""
Error handling: every error reaches the frontend as {"status": 409, "message": "..."}.
Same job as GlobalExceptionHandler + ApiException in the Spring Boot version.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("skillswap.errors")


class ApiError(Exception):
    """Raised by services when a business rule is broken. Carries the HTTP status to return."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message

    # Short, readable factory methods: raise ApiError.conflict("...")
    @classmethod
    def bad_request(cls, message: str): return cls(400, message)
    @classmethod
    def unauthorized(cls, message: str = "Please sign in to continue."): return cls(401, message)
    @classmethod
    def forbidden(cls, message: str): return cls(403, message)
    @classmethod
    def not_found(cls, message: str): return cls(404, message)
    @classmethod
    def conflict(cls, message: str): return cls(409, message)
    @classmethod
    def too_many(cls, message: str): return cls(429, message)
    @classmethod
    def unavailable(cls, message: str): return cls(503, message)


def _body(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"status": status, "message": message})


def _validation_message(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = err.get("loc", ())
        if err.get("type") == "json_invalid" or (loc and loc[0] == "path"):
            return "The request data is not in the expected format."
        if loc == ("body",):
            return "The request body is missing or not in the expected format."
        field = str(loc[-1]) if loc else "request"
        msg = err.get("msg", "is invalid").removeprefix("Value error, ")
        parts.append(f"{field}: {msg}")
    return "; ".join(parts) or "Some fields are invalid."


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError):
        return _body(exc.status, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError):
        return _body(400, _validation_message(exc))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: StarletteHTTPException):
        # FastAPI's own errors: 404 unknown route, 405 wrong method, ...
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _body(exc.status_code, message)

    @app.exception_handler(Exception)
    async def handle_other(_: Request, exc: Exception):
        log.exception("Unhandled error", exc_info=exc)
        return _body(500, "Something went wrong on the server. Try again.")
