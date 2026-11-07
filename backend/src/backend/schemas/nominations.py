"""Nomination timetables and a member's own application to vie."""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from backend.models import AspirantStatus, Seat
from backend.schemas.aspirants import DocumentRead
from backend.schemas.common import WriteModel


class SeatFee(BaseModel):
    seat: Seat
    fee_kes: int = Field(default=0, ge=0, le=10_000_000)


class WindowWrite(WriteModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    opens_on: date
    closes_on: date
    requirements: str = Field(default="", max_length=5000)
    seats: list[SeatFee] = Field(min_length=1, max_length=5)


class WindowRead(BaseModel):
    id: uuid.UUID
    title: str
    opens_on: date
    closes_on: date
    requirements: str
    status: str
    published_at: datetime | None
    seats: list[SeatFee]
    mine: bool = False


class PublicWindow(BaseModel):
    title: str
    opens_on: date
    closes_on: date
    requirements: str
    open: bool
    seats: list[SeatFee]


class FeePaid(WriteModel):
    reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)]


class ApplyFor(WriteModel):
    seat: Seat


class Declaration(WriteModel):
    declaration: bool


class SeatChoice(BaseModel):
    seat: Seat
    fee_kes: int
    area: str


class MyApplication(BaseModel):
    id: uuid.UUID
    seat: Seat
    area: str
    status: AspirantStatus
    status_reason: str | None
    fee_kes: int
    fee_paid: bool
    # A code the member reported, waiting for the office to confirm it.
    fee_waiting: bool = False
    declared_at: datetime | None
    from_window: bool
    documents: list[DocumentRead]


class MyNomination(BaseModel):
    """What the member's account shows: the window, the seats they may apply for, and their
    application."""

    window: PublicWindow | None
    choices: list[SeatChoice]
    application: MyApplication | None
