"""Work given to mobilizers and agents."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import Field, StrictInt, StringConstraints

from backend.models.enums import AssignmentKind, AssignmentStatus
from backend.schemas.common import ORMModel, WriteModel


class AssignmentCreate(WriteModel):
    """One of `mobilizer` or `agent`. An event names its event; ward work its ward (or centre);
    an activity its description, at the member's own place."""

    campaign: uuid.UUID
    mobilizer: uuid.UUID | None = None
    agent: uuid.UUID | None = None
    kind: AssignmentKind
    event: uuid.UUID | None = None
    ward: uuid.UUID | None = None
    registration_centre: uuid.UUID | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    amount_kes: StrictInt = Field(gt=0, le=1_000_000)


class AssignmentRead(ORMModel):
    id: uuid.UUID
    kind: AssignmentKind
    label: str
    member_name: str
    member_role: str
    ward_name: str | None
    centre_name: str | None
    amount_kes: int
    status: AssignmentStatus
    done_at: datetime | None
    created_at: datetime
