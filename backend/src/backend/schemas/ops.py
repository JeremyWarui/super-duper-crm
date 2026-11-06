"""The console's Health, Export and test screens."""

import uuid
from datetime import datetime

from pydantic import Field

from backend.schemas.common import ORMModel, WriteModel


class MigrationState(ORMModel):
    current: str | None
    head: str | None
    up_to_date: bool


class DatabaseState(ORMModel):
    reachable: bool
    detail: str
    size_bytes: int | None


class ServiceHealth(ORMModel):
    key: str
    label: str
    mode: str
    configured: bool


class LastBackup(ORMModel):
    at: datetime
    status: str
    path: str
    size: int
    detail: str


class Disk(ORMModel):
    label: str
    path: str
    free_bytes: int
    total_bytes: int


class Health(ORMModel):
    version: str
    migration: MigrationState
    database: DatabaseState
    organisation_type: str | None
    services: list[ServiceHealth]
    last_backup: LastBackup | None
    disks: list[Disk]


class BackupRunRead(ORMModel):
    id: uuid.UUID
    status: str
    path: str
    size: int
    detail: str
    created_at: datetime
    finished_at: datetime | None


class TestSend(WriteModel):
    phone: str = Field(min_length=3, max_length=20)


class TestResult(ORMModel):
    message: str
