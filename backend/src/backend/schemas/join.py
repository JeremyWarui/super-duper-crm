"""The public sign-up page an event's QR code or a campaign's link opens."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, field_validator

from backend.schemas.common import WriteModel


class JoinPlace(BaseModel):
    id: uuid.UUID
    name: str


class JoinRead(BaseModel):
    """What the page shows: whose campaign, which event, and whether it still takes sign-ups.

    On a campaign's link `place` says whether to ask for a ward or a centre, from `places`.
    """

    campaign_title: str
    candidate_name: str
    event_title: str
    ward_name: str
    open: bool
    place: Literal["ward", "centre"] | None = None
    places: list[JoinPlace] = []


class JoinCreate(WriteModel):
    full_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
    ]
    phone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    consent_given: bool
    # The ward or centre picked on a campaign's link; ignored on an event's.
    place: uuid.UUID | None = None

    @field_validator("consent_given")
    @classmethod
    def _consent_is_required(cls, value: bool) -> bool:
        # Data Protection Act 2019.
        if not value:
            raise ValueError("Consent is required before we can store these details.")
        return value


class JoinDone(BaseModel):
    """`withdraw_code` opens the person's withdrawal page."""

    message: str
    withdraw_code: str


class Withdrawn(BaseModel):
    message: str
