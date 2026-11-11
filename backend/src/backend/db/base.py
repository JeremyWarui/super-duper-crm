"""Declarative base and the column mixins every model uses."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Uuid,
    false,
    func,
    inspect,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint and index names for Alembic.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={getattr(self, 'id', None)}>"


class UUIDPrimaryKeyMixin:
    """A UUID primary key, set when the object is created."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, sort_order=-100
    )

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("id", uuid.uuid4())
        super().__init__(**kwargs)


def updated_at_column() -> Mapped[datetime]:
    """A row's last change, set on insert and on every update."""
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=101,
    )


class OneTimeToken:
    """A secret kept only as its SHA-256, live until it expires or is used."""

    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class TimestampMixin:
    """`created_at`, set by the database clock on insert."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=100,
    )


def choice_type(enum_cls: type, name: str, length: int = 20) -> "SAEnum":
    """Store an enum as VARCHAR with a CHECK constraint listing the valid values."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=length,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
        create_constraint=True,
    )


def require_loaded(instance: object, *attributes: str) -> None:
    """Name the missing `selectinload` instead of failing with `MissingGreenlet`."""
    unloaded = inspect(instance).unloaded
    missing = [name for name in attributes if name in unloaded]
    if missing:
        raise RuntimeError(
            f"{type(instance).__name__}.{'/'.join(missing)} is not loaded. "
            f"Eager-load it, e.g. selectinload({type(instance).__name__}.{missing[0]})."
        )


def partial_unique(name: str, *columns: str, where: str) -> Index:
    """A unique index over `columns` for the rows matching `where`, on Postgres and SQLite."""
    return Index(
        name, *columns, unique=True, postgresql_where=text(where), sqlite_where=text(where)
    )


def user_ref():  # type: ignore[no-untyped-def]
    """Who did something: a login, kept as None when that login is deleted."""
    return mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None)


def campaign_ref():  # type: ignore[no-untyped-def]
    """The campaign a row belongs to; the row goes when the campaign does."""
    return mapped_column(Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)


def file_ref():  # type: ignore[no-untyped-def]
    """An uploaded file, kept as None when the file is deleted."""
    return mapped_column(Uuid, ForeignKey("stored_files.id", ondelete="SET NULL"), default=None)


def starts_false():  # type: ignore[no-untyped-def]
    """A flag that is False until set, in Python and in the database."""
    return mapped_column(Boolean, default=False, server_default=false())
