"""Every error leaves as {"detail": "<one readable sentence>"}."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _describe(error: dict) -> str:
    location = [str(part) for part in error.get("loc", ()) if part not in ("body", "query")]
    field = ".".join(location)
    message = error.get("msg", "Invalid value.")
    return f"{field}: {message}" if field else message


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(_describe(error) for error in exc.errors()) or "Request failed."
        return JSONResponse({"detail": detail}, status_code=status.HTTP_400_BAD_REQUEST)
