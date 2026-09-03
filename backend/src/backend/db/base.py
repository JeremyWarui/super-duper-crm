"""Declarative base, shared column mixins, and the constraint naming scheme."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, Uuid, func, inspect
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names. Without this, Alembic autogenerate cannot
# emit a DROP for an unnamed constraint the database invented for itself.
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
    """UUID primary key, generated client-side.

    CockroachDB spreads writes by key range, so a monotonically increasing
    integer key funnels every insert into one range. `sqlalchemy.Uuid` maps to
    native `UUID` on Postgres/CockroachDB and to `CHAR(32)` on SQLite, so the
    same models run against the test database.

    Generated in Python, not by a server default, and generated in `__init__`
    rather than at flush time: a new object therefore has its id the moment it
    is constructed, so a caller can reference it before anything touches the
    database. `mapped_column(default=...)` alone would not do this - a column
    default only fires during the INSERT.

    SQLAlchemy does not call `__init__` when it loads a row, so this cannot
    overwrite an id that came from the database.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, sort_order=-100
    )

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("id", uuid.uuid4())
        super().__init__(**kwargs)


class TimestampMixin:
    """`created_at` set by the database clock, matching Django's auto_now_add."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=100,
    )


def choice_type(enum_cls: type, name: str, length: int = 20) -> "SAEnum":
    """VARCHAR + CHECK constraint for a `StrEnum`, not a native database enum.

    Django stored choices as `varchar(max_length)` with validation in Python
    only. Keeping VARCHAR preserves that column type (so no data migration) and
    avoids CockroachDB's awkward `ALTER TYPE` path, while the CHECK constraint
    moves the validation Django never enforced into the database.
    """
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
    """Fail loudly when a derived property needs an unloaded relationship.

    Under an AsyncSession a lazy load from attribute access raises
    `MissingGreenlet`, which reads like a concurrency bug rather than a missing
    `selectinload`. This turns it into a sentence that names the fix.
    """
    unloaded = inspect(instance).unloaded
    missing = [name for name in attributes if name in unloaded]
    if missing:
        raise RuntimeError(
            f"{type(instance).__name__}.{'/'.join(missing)} is not loaded. "
            f"Eager-load it, e.g. selectinload({type(instance).__name__}.{missing[0]})."
        )
