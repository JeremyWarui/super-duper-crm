"""One candidate contesting one office in one place."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
    and_,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    choice_type,
    partial_unique,
    require_loaded,
    user_ref,
)
from backend.models.enums import OfficeLevel, OperationalGrain, Seat, UserRole, WorkspaceKind
from backend.models.geography import SeatPlaces
from backend.models.membership import CampaignMember
from backend.models.user import User
from backend.security import new_short_code

if TYPE_CHECKING:
    from backend.models.event import Event
    from backend.models.geography import Constituency, County, Ward
    from backend.models.mobilizer import Mobilizer
    from backend.models.supporter import Supporter
    from backend.models.target import Target


def _seat_for_level(level: OfficeLevel) -> Seat | None:
    """The seat a campaign created by area alone is taken to be; none for the national scope."""
    return {
        OfficeLevel.WARD: Seat.MCA,
        OfficeLevel.CONSTITUENCY: Seat.MP,
        OfficeLevel.COUNTY: Seat.GOVERNOR,
    }.get(level)


# Hosted and standalone campaigns need a seat: a CHECK passes on NULL, so it is tested first.
SEAT_MATCHES_SCOPE = (
    "(kind = 'party' AND seat IS NULL AND office_level = 'national') "
    "OR (kind <> 'party' AND seat IS NOT NULL AND ("
    "(seat = 'mca' AND office_level = 'ward') "
    "OR (seat = 'mp' AND office_level = 'constituency') "
    "OR (seat IN ('governor', 'senator', 'women_rep') AND office_level = 'county')))"
)
SINGLE_KINDS = "kind <> 'hosted'"


# The attribute naming the area a seat at each office level contests.
AREA_FIELD = {
    OfficeLevel.COUNTY: "county",
    OfficeLevel.CONSTITUENCY: "constituency",
    OfficeLevel.WARD: "ward",
}


class Campaign(SeatPlaces, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint(SEAT_MATCHES_SCOPE, name="seat_matches_scope"),
        # One party workspace and one standalone workspace at most.
        partial_unique(
            "uq_campaigns_one_party_one_standalone",
            "kind",
            where=SINGLE_KINDS,
        ),
    )

    title: Mapped[str] = mapped_column(String(150))
    kind: Mapped[WorkspaceKind] = mapped_column(
        choice_type(WorkspaceKind, "workspace_kind"), default=WorkspaceKind.HOSTED
    )
    office_level: Mapped[OfficeLevel] = mapped_column(choice_type(OfficeLevel, "office_level"))
    # The office itself; office_level is the area it is fought over. None for the party.
    seat: Mapped[Seat | None] = mapped_column(choice_type(Seat, "seat"))

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

    # The campaign-wide sign-up link, for posters and shared messages; closed until opened.
    signup_code: Mapped[str] = mapped_column(String(24), unique=True, default=new_short_code)
    signups_open: Mapped[bool] = mapped_column(Boolean, default=False)
    # The team sign-up link mobilizers and agents register through; replacing it retires the old.
    team_code: Mapped[str] = mapped_column(String(24), unique=True, default=new_short_code)

    # Closed after the election: read-only from then on.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    closed_by_id: Mapped[uuid.UUID | None] = user_ref()
    # Months after closing before supporter personal data may be erased.
    retention_months: Mapped[int] = mapped_column(Integer, default=6, server_default=text("6"))
    supporters_erased_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    # The member whose role is candidate; read-only.
    candidate: Mapped[User | None] = relationship(
        secondary=CampaignMember.__table__,
        primaryjoin=lambda: and_(
            Campaign.id == CampaignMember.campaign_id,
            CampaignMember.role == UserRole.CANDIDATE,
        ),
        secondaryjoin=lambda: User.id == CampaignMember.user_id,
        viewonly=True,
        uselist=False,
    )

    members: Mapped[list[CampaignMember]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True
    )
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

    def __init__(self, **kwargs) -> None:
        if kwargs.get("seat") is not None:
            kwargs["seat"] = Seat(kwargs["seat"])
        elif kwargs.get("office_level") is not None:
            kwargs["seat"] = _seat_for_level(OfficeLevel(kwargs["office_level"]))
        super().__init__(**kwargs)

    def __str__(self) -> str:
        return self.title

    @property
    def seat_label(self) -> str:
        """ "MP seat", or "National" for the party workspace, which contests no seat."""
        return f"{self.seat.label} seat" if self.seat is not None else "National"

    @property
    def area(self) -> "County | Constituency | Ward | None":
        """The county, constituency or ward contested, None nationally; needs it loaded."""
        attribute = AREA_FIELD.get(self.office_level)
        if attribute is None:
            return None
        require_loaded(self, attribute)
        return getattr(self, attribute)

    @property
    def candidate_label(self) -> str:
        """The candidate's name, or "" without one; needs `candidate` loaded."""
        return self.candidate.display_name if self.candidate is not None else ""

    @property
    def operational_grain(self) -> OperationalGrain:
        """Ward races organize by registration centre, higher offices by ward."""
        if self.office_level is OfficeLevel.WARD:
            return OperationalGrain.CENTRE
        return OperationalGrain.WARD
