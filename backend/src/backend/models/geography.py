"""The geographic hierarchy: county, constituency, ward, and where people vote."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.event import Event
    from backend.models.mobilizer import Mobilizer
    from backend.models.supporter import Supporter
    from backend.models.target import Target

NON_NEGATIVE_VOTERS = "registered_voters IS NULL OR registered_voters >= 0"


class County(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "counties"
    __table_args__ = (
        CheckConstraint(NON_NEGATIVE_VOTERS, name="registered_voters_non_negative"),
        CheckConstraint(
            "turnout_2022_pct IS NULL OR (turnout_2022_pct >= 0 AND turnout_2022_pct <= 100)",
            name="turnout_pct_range",
        ),
    )

    name: Mapped[str] = mapped_column(String(100), index=True)
    code: Mapped[str] = mapped_column(String(10), default="")
    registered_voters: Mapped[int | None] = mapped_column(Integer, default=None)
    turnout_2022_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)

    constituencies: Mapped[list["Constituency"]] = relationship(
        back_populates="county",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="county")

    def __str__(self) -> str:
        return self.name


class Constituency(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "constituencies"

    county_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("counties.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), index=True)
    code: Mapped[str] = mapped_column(String(10), default="")

    county: Mapped["County"] = relationship(back_populates="constituencies")
    wards: Mapped[list["Ward"]] = relationship(
        back_populates="constituency",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="constituency")

    def __str__(self) -> str:
        return self.name


class Ward(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "wards"
    __table_args__ = (CheckConstraint(NON_NEGATIVE_VOTERS, name="registered_voters_non_negative"),)

    constituency_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("constituencies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), index=True)
    code: Mapped[str] = mapped_column(String(10), default="")
    registered_voters: Mapped[int | None] = mapped_column(Integer, default=None)

    constituency: Mapped["Constituency"] = relationship(back_populates="wards")
    polling_stations: Mapped[list["PollingStation"]] = relationship(
        back_populates="ward", cascade="all, delete-orphan", passive_deletes=True
    )
    centres: Mapped[list["RegistrationCentre"]] = relationship(
        back_populates="ward", cascade="all, delete-orphan", passive_deletes=True
    )
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="ward")
    targets: Mapped[list["Target"]] = relationship(
        back_populates="ward", cascade="all, delete-orphan", passive_deletes=True
    )
    mobilizers: Mapped[list["Mobilizer"]] = relationship(
        back_populates="ward", cascade="all, delete-orphan", passive_deletes=True
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="ward", cascade="all, delete-orphan", passive_deletes=True
    )
    supporters: Mapped[list["Supporter"]] = relationship(back_populates="ward")

    def __str__(self) -> str:
        return f"{self.name} - {self.constituency.name}"


class RegistrationCentre(UUIDPrimaryKeyMixin, Base):
    """A venue such as a school or church hall, holding several polling stations.

    This is the unit a ward (MCA) campaign organizes on.
    """

    __tablename__ = "registration_centres"
    __table_args__ = (CheckConstraint(NON_NEGATIVE_VOTERS, name="registered_voters_non_negative"),)

    ward_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(30), default="")
    name: Mapped[str] = mapped_column(String(200))
    registered_voters: Mapped[int | None] = mapped_column(Integer, default=None)

    ward: Mapped["Ward"] = relationship(back_populates="centres")
    targets: Mapped[list["Target"]] = relationship(
        back_populates="registration_centre", cascade="all, delete-orphan", passive_deletes=True
    )
    mobilizers: Mapped[list["Mobilizer"]] = relationship(back_populates="registration_centre")
    events: Mapped[list["Event"]] = relationship(back_populates="registration_centre")

    def __str__(self) -> str:
        return f"{self.name} - {self.ward.name}"


class PollingStation(UUIDPrimaryKeyMixin, Base):
    """A single voting stream within a ward.

    `centre_code` and `centre_name` name the venue as free text rather than
    linking to `RegistrationCentre`. See the README.
    """

    __tablename__ = "polling_stations"
    __table_args__ = (CheckConstraint(NON_NEGATIVE_VOTERS, name="registered_voters_non_negative"),)

    ward_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="CASCADE"), index=True
    )
    centre_code: Mapped[str] = mapped_column(String(30), default="")
    centre_name: Mapped[str] = mapped_column(String(200), default="")
    code: Mapped[str] = mapped_column(String(30), default="")
    name: Mapped[str] = mapped_column(String(200))
    registered_voters: Mapped[int | None] = mapped_column(Integer, default=None)

    ward: Mapped["Ward"] = relationship(back_populates="polling_stations")

    def __str__(self) -> str:
        return f"{self.name} - {self.ward.name}"
