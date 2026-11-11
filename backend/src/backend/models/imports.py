"""Reference data imports and the change each one made, and backups of the installation."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, user_ref


class ImportRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One boundary or register file applied; `counts` is changes per kind."""

    __tablename__ = "import_runs"

    kind: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(255), default="")
    sha256: Mapped[str] = mapped_column(String(64))
    rows: Mapped[int] = mapped_column(Integer)
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    actor_id: Mapped[uuid.UUID | None] = user_ref()

    changes: Mapped[list["ImportChange"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class ImportChange(UUIDPrimaryKeyMixin, Base):
    """One row the import created, renamed, moved, retired, restored or re-counted."""

    __tablename__ = "import_changes"

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("import_runs.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(50))
    change: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(Text, default="")

    run: Mapped["ImportRun"] = relationship(back_populates="changes")


class BackupRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One `campaign-crm backup`: the archive it wrote, or why it failed."""

    __tablename__ = "backup_runs"

    status: Mapped[str] = mapped_column(String(20))
    path: Mapped[str] = mapped_column(String(500), default="")
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
