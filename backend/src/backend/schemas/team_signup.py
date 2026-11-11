"""The public team sign-up page, the registration queue, and polling agents."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from backend.models.enums import AgentStatus, FieldRole, RegistrationStatus
from backend.schemas.common import Invite, ORMModel, Phone, WriteModel, plain_text

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class SignupPlace(BaseModel):
    id: uuid.UUID
    name: str
    county_name: str = ""


class SignupRead(BaseModel):
    """What the team sign-up page shows. A mobilizer picks a ward, or a centre in an MCA race
    (`mobilizer_place`); an agent always picks a centre, ward first."""

    campaign_title: str
    seat_label: str
    open: bool
    consent_wording: str
    mobilizer_place: Literal["ward", "centre"]
    wards: list[SignupPlace]


class SignupCreate(WriteModel):
    role: FieldRole
    first_name: Annotated[Name, AfterValidator(plain_text)]
    last_name: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=150), AfterValidator(plain_text)
    ] = ""
    phone: Phone
    email: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=254),
        AfterValidator(plain_text),
    ]
    # A national ID or passport number.
    id_number: Annotated[
        str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9]{5,12}$")
    ]
    ward: uuid.UUID | None = None
    registration_centre: uuid.UUID | None = None
    consent_given: bool


class SignupDone(BaseModel):
    message: str


class RegistrationRead(ORMModel):
    """`id_number` is None for a role without `team.id_read`."""

    id: uuid.UUID
    role: FieldRole
    full_name: str
    phone: str
    email: str
    id_number: str | None
    ward_name: str | None
    centre_name: str | None
    status: RegistrationStatus
    reason: str
    created_at: datetime


class Rejection(WriteModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class Approved(BaseModel):
    """`placed` is False when the mobilizer's ward or centre already had someone."""

    registration: RegistrationRead
    invite: Invite
    placed: bool


class TeamLink(BaseModel):
    code: str


class AgentRead(ORMModel):
    """`id_number` is None for a role without `team.id_read`."""

    id: uuid.UUID
    full_name: str
    phone: str
    email: str
    id_number: str | None
    registration_centre: uuid.UUID | None
    centre_name: str | None
    ward_name: str | None
    status: AgentStatus
    training_date: date | None


class AgentUpdate(WriteModel):
    registration_centre: uuid.UUID | None = None
    status: AgentStatus | None = None
    training_date: date | None = None


class CoverageCentre(BaseModel):
    id: uuid.UUID
    name: str
    ward_name: str


class Coverage(BaseModel):
    """Centres in the caller's reach, how many have an agent, and up to `LIMIT` without one."""

    centres: int
    covered: int
    uncovered: list[CoverageCentre] = Field(default_factory=list)
    more_uncovered: int = 0
