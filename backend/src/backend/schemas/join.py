"""The public sign-up page an event's QR code opens."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from backend.schemas.common import WriteModel


class JoinRead(BaseModel):
    """What the page shows: whose campaign, which event, and whether it still takes sign-ups."""

    campaign_title: str
    candidate_name: str
    event_title: str
    ward_name: str
    open: bool


class JoinCreate(WriteModel):
    full_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
    ]
    phone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    consent_given: bool

    @field_validator("consent_given")
    @classmethod
    def _consent_is_required(cls, value: bool) -> bool:
        # Data Protection Act 2019.
        if not value:
            raise ValueError("Consent is required before we can store these details.")
        return value


class JoinDone(BaseModel):
    message: str
