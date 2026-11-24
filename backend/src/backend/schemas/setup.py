"""The first-run setup's request and answers."""

import uuid
from datetime import date

from pydantic import Field, model_validator

from backend.models import Seat
from backend.schemas.common import (
    CampaignTitle,
    LoginDetails,
    Named,
    ORMModel,
    Password,
    WriteModel,
    plain_text,
)
from backend.schemas.content import Link
from backend.schemas.site import Email, SiteIdentity, refuse_low_contrast


class SetupToken(WriteModel):
    token: str = Field(min_length=1, max_length=200)


class SetupSite(SiteIdentity):
    """Step 2 and 3: name, logo, colours, contacts and privacy notice."""

    logo_url: Link = ""

    @model_validator(mode="after")
    def _checked(self) -> "SetupSite":
        for name in ("name", "short_name", "contact_phone", "address"):
            setattr(self, name, plain_text(getattr(self, name)).strip())
        refuse_low_contrast(self.primary_colour, self.secondary_colour)
        return self


class SetupSuperuser(WriteModel):
    """Step 4: the first console login, which signs in with this email and password."""

    username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9._-]+$")
    email: Email = Field(min_length=3)
    password: Password
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)


class InvitedLogin(LoginDetails):
    """A login sent an invite link, so it needs an email."""

    email: str = Field(min_length=3, max_length=254)


class SetupSeat(WriteModel):
    """Step 5: the seat, its area, the election and the candidate's login."""

    title: CampaignTitle
    seat: Seat
    election_date: date | None = None
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None
    candidate: InvitedLogin


class SetupRequest(SetupToken):
    site: SetupSite
    superuser: SetupSuperuser
    campaign: SetupSeat


Area = Named


class ServiceState(ORMModel):
    """One outside service: `mode` is the provider `.env` picks; `live` when it really sends."""

    key: str
    label: str
    mode: str
    live: bool
    testable: bool


class SetupResult(ORMModel):
    superuser: str
    workspace: uuid.UUID
    # How each invite link went out: "email", or "none".
    invites: list[str]
    services: list[ServiceState]


class ServiceTestResult(ORMModel):
    message: str


class PreviewSeat(WriteModel):
    """The seat setup is about to create, for its target preview."""

    seat: Seat
    election_date: date | None = None
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None


class PastResult(ORMModel):
    year: int
    valid_votes: int
    winner_share_pct: str | None


class PreviewScenario(ORMModel):
    scenario: str
    turnout_pct: str
    projected: int
    competitive: int
    majority: int
    target: int


class PreviewUnit(ORMModel):
    name: str
    weight_pct: str
    target: int


class TargetPreview(ORMModel):
    """What setup will save as the seat's targets, before anything is saved."""

    seat: str
    registered_voters: int
    results: list[PastResult]
    share_pct: str
    typical_pct: str | None
    reliability: str
    two_candidate: bool
    turnout_pct: str
    scenarios: list[PreviewScenario]
    seat_target: int
    units: list[PreviewUnit]
    note: str | None
