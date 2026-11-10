"""Every error leaves as {"detail": "<one readable sentence>"}."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from backend.services.errors import CampaignClosed, Forbidden, NotFound, Refused, TooLarge

# Each uniqueness rule a request can race past: the names Postgres and SQLite give its index,
# and the sentence it answers with. The first match wins, so the one-manager rule comes before
# the one-place rule: SQLite names only the column they share.
UNIQUE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("uq_campaign_members_one_campaign_per_user", "campaign_members.user_id"),
        "That login is already on a campaign; a login belongs to one campaign.",
    ),
    (("uq_campaign_members_one_manager",), "That campaign already has a manager."),
    (("campaign_members.campaign_id",), "That campaign already has its aspirant or its manager."),
    (
        ("uq_supporters_campaign_phone", "supporters.campaign_id, supporters.phone"),
        "That phone number is already on this campaign's register.",
    ),
    (
        ("uq_aspirants_one_live_per_member", "aspirants.member_id"),
        "That member already has a live nomination.",
    ),
    (
        ("uq_aspirants_campaign_id", "aspirants.campaign_id"),
        "That aspirant already has a workspace.",
    ),
    (
        ("uq_party_members_phone", "party_members.phone"),
        "That phone number is already on the party register.",
    ),
    (
        ("uq_payments_event_mobilizer", "payments.event_id, payments.mobilizer_id"),
        "That mobilizer already has a payment for this event.",
    ),
    (
        (
            "uq_mobilizers_campaign_ward",
            "uq_mobilizers_campaign_registration_centre",
            "mobilizers.campaign_id, mobilizers.ward_id",
            "mobilizers.campaign_id, mobilizers.registration_centre_id",
        ),
        "That ward already has a mobilizer.",
    ),
    (
        ("pk_party_roles", "party_roles.user_id, party_roles.role"),
        "That login already holds that party office.",
    ),
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
        elif isinstance(exc, TooLarge):
            code = status.HTTP_413_CONTENT_TOO_LARGE
        return _detail(str(exc), code)

    @app.exception_handler(CampaignClosed)
    async def _campaign_closed(_: Request, exc: CampaignClosed) -> JSONResponse:
        return JSONResponse(
            {"detail": str(exc), "code": exc.code},
            status_code=status.HTTP_403_FORBIDDEN,
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        """A request that raced past a uniqueness check still answers with the rule."""
        raised = str(exc.orig)
        for names, message in UNIQUE_RULES:
            if any(name in raised for name in names):
                return _detail(message, status.HTTP_400_BAD_REQUEST)
        raise exc
