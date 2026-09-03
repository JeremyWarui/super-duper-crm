"""One candidate contesting one office in one place."""

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    choice_type,
    require_loaded,
)
from backend.models.enums import OfficeLevel, OperationalGrain

if TYPE_CHECKING:
    from backend.models.event import Event
    from backend.models.geography import Constituency, County, Ward
    from backend.models.mobilizer import Mobilizer
    from backend.models.supporter import Supporter
    from backend.models.target import Target
    from backend.models.user import User


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(150))
    office_level: Mapped[OfficeLevel] = mapped_column(choice_type(OfficeLevel, "office_level"))

    # office_level decides which one of these three applies.
    county_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("counties.id", ondelete="SET NULL"), default=None, index=True
    )
    constituency_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("constituencies.id", ondelete="SET NULL"), default=None, index=True
    )
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="SET NULL"), default=None, index=True
    )

    election_date: Mapped[date | None] = mapped_column(Date, default=None)

    candidate: Mapped["User"] = relationship(back_populates="campaigns")
    county: Mapped["County | None"] = relationship(back_populates="campaigns")
    constituency: Mapped["Constituency | None"] = relationship(back_populates="campaigns")
    ward: Mapped["Ward | None"] = relationship(back_populates="campaigns")

    targets: Mapped[list["Target"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True
    )
    mobilizers: Mapped[list["Mobilizer"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True
    )
    supporters: Mapped[list["Supporter"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True
    )

    def __str__(self) -> str:
        return self.title

    @property
    def area(self) -> "County | Constituency | Ward | None":
        """The place this campaign contests, picked by its office level.

        The matching relationship must be loaded.
        """
        attribute = {
            OfficeLevel.WARD: "ward",
            OfficeLevel.CONSTITUENCY: "constituency",
            OfficeLevel.COUNTY: "county",
        }[self.office_level]
        require_loaded(self, attribute)
        return getattr(self, attribute)

    @property
    def operational_grain(self) -> OperationalGrain:
        """Ward races organize by registration centre, higher offices by ward."""
        if self.office_level is OfficeLevel.WARD:
            return OperationalGrain.CENTRE
        return OperationalGrain.WARD
