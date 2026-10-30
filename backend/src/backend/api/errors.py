"""Every error leaves as {"detail": "<one readable sentence>"}."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from backend.services.errors import Forbidden, NotFound, Refused

# The one-campaign index, as Postgres and SQLite name it.
ONE_CAMPAIGN = ("uq_campaign_members_one_campaign_per_user", "campaign_members.user_id")
# One manager per campaign. SQLite names only the column, which the one-candidate index shares.
ONE_MANAGER = ("uq_campaign_members_one_manager",)
ONE_PLACE = ("campaign_members.campaign_id",)
# One supporter per phone per campaign, as Postgres and SQLite name it.
ONE_SUPPORTER = ("uq_supporters_campaign_phone", "supporters.campaign_id, supporters.phone")
# One of each party office per login, as Postgres and SQLite name it.
ONE_OFFICE = ("pk_party_roles", "party_roles.user_id, party_roles.role")
# One live payment per mobilizer per event, as Postgres and SQLite name it.
ONE_PAYMENT = ("uq_payments_event_mobilizer", "payments.event_id, payments.mobilizer_id")
# The one-mobilizer-per-unit indexes, as Postgres and SQLite name them.
ONE_MOBILIZER = (
    "uq_mobilizers_campaign_ward",
    "uq_mobilizers_campaign_registration_centre",
    "mobilizers.campaign_id, mobilizers.ward_id",
    "mobilizers.campaign_id, mobilizers.registration_centre_id",
)


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
        code = status.HTTP_400_BAD_REQUEST
        if isinstance(exc, NotFound):
            code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, Forbidden):
            code = status.HTTP_403_FORBIDDEN
        return _detail(str(exc), code)

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        """A request that raced past a uniqueness check still answers with the rule."""
        if any(name in str(exc.orig) for name in ONE_CAMPAIGN):
            return _detail(
                "That login is already on a campaign; a login belongs to one campaign.",
                status.HTTP_400_BAD_REQUEST,
            )
        if any(name in str(exc.orig) for name in ONE_MANAGER):
            return _detail("That campaign already has a manager.", status.HTTP_400_BAD_REQUEST)
        if any(name in str(exc.orig) for name in ONE_PLACE):
            return _detail(
                "That campaign already has its aspirant or its manager.",
                status.HTTP_400_BAD_REQUEST,
            )
        if any(name in str(exc.orig) for name in ONE_SUPPORTER):
            return _detail(
                "That phone number is already on this campaign's register.",
                status.HTTP_400_BAD_REQUEST,
            )
        if any(name in str(exc.orig) for name in ONE_PAYMENT):
            return _detail(
                "That mobilizer already has a payment for this event.",
                status.HTTP_400_BAD_REQUEST,
            )
        if any(name in str(exc.orig) for name in ONE_MOBILIZER):
            return _detail("That ward already has a mobilizer.", status.HTTP_400_BAD_REQUEST)
        if any(name in str(exc.orig) for name in ONE_OFFICE):
            return _detail(
                "That login already holds that party office.", status.HTTP_400_BAD_REQUEST
            )
        raise exc
