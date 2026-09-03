"""Declarative base and the column mixins every model uses."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, Uuid, func, inspect
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Gives every constraint and index a predictable name, which Alembic needs in
# order to alter or drop one.
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
    """A UUID primary key, generated in Python when the object is created.

    Set in `__init__` rather than on insert, so an object has its id before it
    is saved.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, sort_order=-100
    )

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("id", uuid.uuid4())
        super().__init__(**kwargs)


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
    """Raise a readable error when a property needs a relationship that was not loaded.

    Reading an unloaded relationship on an async session fails with
    `MissingGreenlet`; this names the missing `selectinload` instead.
    """
    unloaded = inspect(instance).unloaded
    missing = [name for name in attributes if name in unloaded]
    if missing:
        raise RuntimeError(
            f"{type(instance).__name__}.{'/'.join(missing)} is not loaded. "
            f"Eager-load it, e.g. selectinload({type(instance).__name__}.{missing[0]})."
        )
