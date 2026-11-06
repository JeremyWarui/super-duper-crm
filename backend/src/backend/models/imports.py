"""Reference data imports and the change each one made."""

import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ImportRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One boundary or register file applied; `counts` is changes per kind."""

    __tablename__ = "import_runs"

    kind: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(255), default="")
    sha256: Mapped[str] = mapped_column(String(64))
    rows: Mapped[int] = mapped_column(Integer)
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

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
