"""Every error leaves as {"detail": "<one readable sentence>"}."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

# How each database names the index that holds a login to one campaign.
ONE_CAMPAIGN = ("uq_campaign_members_one_campaign_per_user", "campaign_members.user_id")


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

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        if any(name in str(exc.orig) for name in ONE_CAMPAIGN):
            return JSONResponse(
                {"detail": "That login is already on a campaign; a login belongs to one campaign."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        raise exc
