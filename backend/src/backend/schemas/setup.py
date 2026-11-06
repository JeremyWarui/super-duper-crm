"""The first-run setup's request and answers."""

import uuid
from datetime import date

from pydantic import Field, model_validator

from backend.models import OrganisationType, Seat
from backend.schemas.common import CampaignTitle, LoginDetails, ORMModel, WriteModel, plain_text
from backend.schemas.content import Link
from backend.schemas.site import Colour, Email
from backend.services.branding import INK, MIN_CONTRAST, WHITE, contrast


class SetupToken(WriteModel):
    token: str = Field(min_length=1, max_length=200)


class SetupSite(WriteModel):
    """Step 2 and 3: name, logo, colours, contacts and privacy notice."""

    name: str = Field(min_length=1, max_length=150)
    short_name: str = Field(default="", max_length=30)
    logo_url: Link = ""
    primary_colour: Colour
    secondary_colour: Colour
    contact_email: Email = ""
    contact_phone: str = Field(default="", max_length=20)
    address: str = Field(default="", max_length=300)
    privacy_notice: str = Field(default="", max_length=20000)

    @model_validator(mode="after")
    def _checked(self) -> "SetupSite":
        for name in ("name", "short_name", "contact_phone", "address"):
            setattr(self, name, plain_text(getattr(self, name)).strip())
        if contrast(self.primary_colour, WHITE) < MIN_CONTRAST:
            raise ValueError("The primary colour is too light for white text; pick a darker one.")
        if contrast(self.secondary_colour, INK) < MIN_CONTRAST:
            raise ValueError("The secondary colour is too dark for ink text; pick a lighter one.")
        return self


class SetupSuperuser(WriteModel):
    """Step 4: the first console login, which signs in with this email and password."""

    username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9._-]+$")
    email: Email = Field(min_length=3)
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)


class InvitedLogin(LoginDetails):
    """A login sent an invite link, so it needs an email."""

    email: str = Field(min_length=3, max_length=254)


class SetupSeat(WriteModel):
    """Step 5 for an aspirant: the seat, its area, the election and the candidate's login."""

    title: CampaignTitle
    seat: Seat
    election_date: date | None = None
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None
    candidate: InvitedLogin


class SetupRequest(SetupToken):
    organisation_type: OrganisationType
    site: SetupSite
    superuser: SetupSuperuser
    aspirant: SetupSeat | None = None
    # A party may open its workspace now, with its first Workspace Manager.
    party_workspace: InvitedLogin | None = None

    @model_validator(mode="after")
    def _fits_the_type(self) -> "SetupRequest":
        if self.organisation_type is OrganisationType.ASPIRANT:
            if self.aspirant is None:
                raise ValueError("An aspirant installation needs its seat and candidate.")
            if self.party_workspace is not None:
                raise ValueError("Only a party installation has a party workspace.")
        elif self.aspirant is not None:
            raise ValueError("Only an aspirant installation has a seat.")
        return self


class Area(ORMModel):
    id: uuid.UUID
    name: str


class ServiceState(ORMModel):
    """One outside service: `mode` is the provider `.env` picks; `live` when it really sends."""

    key: str
    label: str
    mode: str
    live: bool
    testable: bool


class SetupResult(ORMModel):
    organisation_type: OrganisationType
    superuser: str
    workspace: uuid.UUID | None
    # How each invite link went out: "email", or "none".
    invites: list[str]
    services: list[ServiceState]


class ServiceTestResult(ORMModel):
    message: str
