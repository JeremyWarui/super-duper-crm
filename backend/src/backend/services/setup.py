"""First-run setup: a one-time token opens it, and one transaction makes the installation."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models import (
    CandidateProfile,
    Constituency,
    County,
    OrganisationType,
    SetupToken,
    SiteSettings,
    User,
    Ward,
    WorkspaceKind,
)
from backend.schemas.setup import Area, ServiceState, SetupRequest, SetupResult
from backend.security import sha256_hex
from backend.services import geography, oidc, party_workspace, texting, tokens
from backend.services.accounts import new_login
from backend.services.admin import build_workspace
from backend.services.audit import record
from backend.services.email import send_email
from backend.services.errors import Forbidden, Refused
from backend.services.sms import require_phone

TOKEN_LIFE = timedelta(hours=24)
DONE = "This installation is already set up."
BAD_TOKEN = (
    "That setup token is wrong, spent or more than 24 hours old. "
    "Print a new one with `campaign-crm setup-token`."
)


async def is_set_up(session: AsyncSession) -> bool:
    return await session.get(SiteSettings, 1) is not None


async def new_token(session: AsyncSession) -> str:
    """A fresh token valid for 24 hours; any earlier unspent token stops working."""
    if await is_set_up(session):
        raise Refused(DONE)
    token = secrets.token_urlsafe(32)
    await session.execute(
        update(SetupToken).where(SetupToken.used_at.is_(None)).values(used_at=datetime.now(UTC))
    )
    session.add(SetupToken(token_hash=sha256_hex(token), expires_at=datetime.now(UTC) + TOKEN_LIFE))
    await session.commit()
    return token


async def check(session: AsyncSession, token: str) -> None:
    """Refused unless setup is still to do and the token is live."""
    if await is_set_up(session):
        raise Refused(DONE)
    row = await session.scalar(select(SetupToken).where(SetupToken.token_hash == sha256_hex(token)))
    if row is None or not tokens.is_live(row.expires_at, row.used_at):
        raise Forbidden(BAD_TOKEN)


async def _spend(session: AsyncSession, token: str) -> None:
    """Marks the token used, once; a second request with it is refused."""
    await check(session, token)
    if not await tokens.spend(
        session,
        SetupToken,
        SetupToken.token_hash == sha256_hex(token),
        SetupToken.used_at.is_(None),
        used_at=datetime.now(UTC),
    ):
        raise Forbidden(BAD_TOKEN)


async def areas(
    session: AsyncSession, token: str, level: str, parent: uuid.UUID | None
) -> list[Area]:
    """Counties, a county's constituencies or a constituency's wards, for picking the seat."""
    await check(session, token)
    model = {"county": County, "constituency": Constituency, "ward": Ward}[level]
    if model is not County and parent is None:
        raise Refused(f"Pick the {'county' if level == 'constituency' else 'constituency'} first.")
    found = await geography.places(session, model, None if model is County else parent)
    return [Area(id=row.id, name=row.name) for row in found]


async def run(session: AsyncSession, payload: SetupRequest) -> SetupResult:
    """Spend the token and make the installation: its settings, first superuser and, for an
    aspirant, the standalone workspace with its candidate page and login; all or nothing."""
    try:
        await _spend(session, payload.token)
        session.add(
            SiteSettings(
                id=1, organisation_type=payload.organisation_type, **payload.site.model_dump()
            )
        )
        await session.flush()
        admin, _ = await new_login(
            session,
            username=payload.superuser.username,
            role=None,
            password=payload.superuser.password,
            email=payload.superuser.email,
            first_name=payload.superuser.first_name,
            last_name=payload.superuser.last_name,
            is_superuser=True,
        )
        workspace_id, invites = None, []
        if payload.organisation_type is OrganisationType.ASPIRANT:
            seat = payload.aspirant
            campaign, _, logins = await build_workspace(
                session,
                aspirant=seat.candidate.model_dump(),
                title=seat.title,
                seat=seat.seat,
                election_date=seat.election_date,
                county=seat.county,
                constituency=seat.constituency,
                ward=seat.ward,
            )
            campaign.kind = WorkspaceKind.STANDALONE
            session.add(CandidateProfile(campaign_id=campaign.id))
            workspace_id, invites = campaign.id, [invite for _, invite in logins]
        elif payload.party_workspace is not None:
            campaign, _, _, invite = await party_workspace.build(
                session, name=payload.site.name, manager=payload.party_workspace.model_dump()
            )
            workspace_id, invites = campaign.id, [invite]
        record(
            session,
            actor=admin,
            action="setup.completed",
            subject_type="site_settings",
            detail={
                "organisation_type": payload.organisation_type.value,
                "workspace": bool(workspace_id),
            },
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise Refused(DONE) from None
    except Refused:
        await session.rollback()
        raise
    return SetupResult(
        organisation_type=payload.organisation_type,
        superuser=admin.username,
        workspace=workspace_id,
        invites=invites,
        services=services(),
    )


def services() -> list[ServiceState]:
    """What `.env` turns on: each outside service, and whether it really sends."""
    settings = get_settings()
    return [
        ServiceState(
            key="email",
            label="Email",
            mode=settings.email_provider,
            live=settings.email_provider == "smtp",
            testable=True,
        ),
        ServiceState(
            key="sms",
            label="SMS",
            mode=settings.sms_provider,
            live=settings.sms_provider == "africastalking",
            testable=True,
        ),
        ServiceState(
            key="payouts",
            label="Payouts (M-Pesa)",
            mode=settings.payout_provider,
            live=settings.payout_provider == "paystack",
            testable=False,
        ),
        ServiceState(
            key="payins",
            label="Payments in (M-Pesa)",
            mode=settings.payin_provider,
            live=settings.payin_provider == "paystack",
            testable=False,
        ),
        ServiceState(
            key="google",
            label="Google sign-in",
            mode="google" if oidc.configured() else "off",
            live=oidc.configured(),
            testable=True,
        ),
    ]


async def _audit_test(session: AsyncSession, user: User, key: str) -> None:
    record(
        session, actor=user, action="setup.test", subject_type="service", detail={"service": key}
    )
    await session.commit()


async def test_service(session: AsyncSession, key: str, user: User) -> str:
    """Send a test email or text to the signed-in superuser; says what happened."""
    if key == "email":
        if not user.email:
            raise Refused("Your login has no email to send the test to.")
        row = await send_email(
            session, user.email, "Test email", "This is a test email from your campaign platform."
        )
        await _audit_test(session, user, key)
        if row.status == "failed":
            raise Refused(f"The email did not send: {row.detail}")
        return (
            "Logged in practice mode; nothing was sent."
            if row.status == "practice"
            else f"Sent to {user.email}."
        )
    if key == "sms":
        phone = require_phone(user.phone, "Your login has no phone number to text.")
        result = await texting.send_test(session, phone, actor=user)
        await _audit_test(session, user, key)
        return texting.test_outcome(result, phone, "Recorded in practice mode; nothing was sent.")
    if key == "google":
        if not oidc.configured():
            raise Refused(
                "Google sign-in is off: add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env."
            )
        try:
            await oidc.metadata()
        except (oidc.OidcError, OSError) as failed:
            raise Refused(f"Google could not be reached: {failed}") from failed
        return (
            f"Google answered. Its OAuth client must allow the redirect URI {oidc.redirect_uri()}"
        )
    raise Refused("That service has no test.")
