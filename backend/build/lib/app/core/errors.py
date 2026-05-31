"""RFC 7807 problem+json error handling (placeholder for Sprint 0).

Centralises HTTP/validation/unhandled error mapping so clients never receive
stack traces or internal messages (see docs/architecture/11 §N error handling).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"


def _problem(status: int, title: str, detail: str | None = None, **extra: object) -> JSONResponse:
    body: dict[str, object] = {"type": "about:blank", "title": title, "status": status}
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_JSON)


def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem(exc.status_code, title=str(exc.detail), detail=None)

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(422, title="Validation error", errors=exc.errors())

    @app.exception_handler(Exception)
    async def _unhandled_exc(_: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
        # Do not leak internals; correlation id wiring comes in a later sprint.
        return _problem(500, title="Internal Server Error")
