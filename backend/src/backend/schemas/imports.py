"""Reference data imports: the file sent, and the report back."""

import uuid
from datetime import datetime

from pydantic import Field

from backend.schemas.common import ORMModel, WriteModel

# A centre-level boundary file for the whole country is about 3 MB.
MAX_CSV = 20_000_000
SHOWN_CHANGES = 500


class ImportUpload(WriteModel):
    filename: str = Field(default="", max_length=255)
    csv: str = Field(min_length=1, max_length=MAX_CSV)
    # Check the file and report what it would change, writing nothing.
    dry_run: bool = False


class ChangeRead(ORMModel):
    level: str
    code: str
    change: str
    detail: str


class ImportReportRead(ORMModel):
    """`changes` lists the first 500; `counts` covers them all."""

    kind: str
    rows: int
    applied: bool
    counts: dict[str, int]
    changes: list[ChangeRead]


class ImportRunRead(ORMModel):
    id: uuid.UUID
    kind: str
    filename: str
    rows: int
    counts: dict[str, int]
    created_at: datetime
