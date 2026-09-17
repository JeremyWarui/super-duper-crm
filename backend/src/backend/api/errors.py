"""Every error leaves as {"detail": "<one readable sentence>"}."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from backend.services.errors import NotFound, Refused

# The one-campaign index, as Postgres and SQLite name it.
ONE_CAMPAIGN = ("uq_campaign_members_one_campaign_per_user", "campaign_members.user_id")


def _describe(error: dict) -> str:
    location = [str(part) for part in error.get("loc", ()) if part not in ("body", "query")]
    field = ".".join(location)
    message = error.get("msg", "Invalid value.")
    return f"{field}: {message}" if field else message


def _detail(message: str, code: int) -> JSONResponse:
    return JSONResponse({"detail": message}, status_code=code)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(_describe(error) for error in exc.errors()) or "Request failed."
        return _detail(detail, status.HTTP_400_BAD_REQUEST)

    @app.exception_handler(Refused)
    async def _refused(_: Request, exc: Refused) -> JSONResponse:
        code = (
            status.HTTP_404_NOT_FOUND if isinstance(exc, NotFound) else status.HTTP_400_BAD_REQUEST
        )
        return _detail(str(exc), code)

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        """A request that raced past the one-campaign check still answers with the rule."""
        if any(name in str(exc.orig) for name in ONE_CAMPAIGN):
            return _detail(
                "That login is already on a campaign; a login belongs to one campaign.",
                status.HTTP_400_BAD_REQUEST,
            )
        raise exc
