import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

log = logging.getLogger("taskflow")


class AppError(Exception):
    """A failure the client should hear about. `fields` maps input names to inline messages."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or {}
        self.headers = headers


def error_response(err: AppError) -> JSONResponse:
    body = {"detail": err.message, "code": err.code, "fields": err.fields}
    return JSONResponse(status_code=err.status, content=body, headers=err.headers)


def _validation_message(error: dict) -> str:
    if error["type"] == "missing":
        return "This field is required"
    return error["msg"].removeprefix("Value error, ")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, err: AppError):
        return error_response(err)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, err: RequestValidationError):
        fields: dict[str, str] = {}
        for error in err.errors():
            location = list(error["loc"])
            if location and location[0] in ("body", "query", "path", "header", "cookie"):
                location = location[1:]  # drop where the input came from, keep the field name
            fields.setdefault(".".join(str(part) for part in location) or "_", _validation_message(error))
        detail = next(iter(fields.values()), "The request is not valid")
        return JSONResponse(
            status_code=422, content={"detail": detail, "code": "validation_error", "fields": fields}
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity(_: Request, err: IntegrityError):
        log.warning("integrity error: %s", err.orig)
        return JSONResponse(
            status_code=409,
            content={
                "detail": "That change conflicts with the current state. Refresh and try again.",
                "code": "conflict",
                "fields": {},
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, err: Exception):
        log.exception("unhandled error", exc_info=err)
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong on our side.", "code": "internal_error", "fields": {}},
        )
