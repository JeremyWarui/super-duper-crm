"""Past election results: shared reference data the competitive target is built on.

Loaded by `campaign-crm seed-results`, never written by a campaign. A contest keeps the IEBC area
codes it was reported under, and links to today's county, constituency or ward when the code
still exists, so a boundary change leaves the history readable.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, UUIDPrimaryKeyMixin, choice_type, starts_false
from backend.models.enums import ResultLevel, ResultOffice


def place_ref(table: str):  # type: ignore[no-untyped-def]
    """Today's place a contest's code matches, kept as None when that place is deleted."""
    return mapped_column(
        Uuid, ForeignKey(f"{table}.id", ondelete="SET NULL"), default=None, index=True
    )


class Election(UUIDPrimaryKeyMixin, Base):
    """One election day's results, e.g. the 2017 General Election or its October presidential."""

    __tablename__ = "elections"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    year: Mapped[int] = mapped_column(Integer, index=True)

    contests: Mapped[list["Contest"]] = relationship(
        back_populates="election", cascade="all, delete-orphan", passive_deletes=True
    )

    def __str__(self) -> str:
        return self.name


class Contest(UUIDPrimaryKeyMixin, Base):
    """One office decided over one area in one election, with its valid-vote total."""

    __tablename__ = "contests"
    __table_args__ = (
        UniqueConstraint(
            "election_id",
            "office",
            "county_code",
            "constituency_code",
            "ward_code",
            name="uq_contests_area",
        ),
        CheckConstraint("total_votes IS NULL OR total_votes >= 0", name="total_votes_non_negative"),
        CheckConstraint(
            "registered_voters IS NULL OR registered_voters >= 0",
            name="registered_voters_non_negative",
        ),
    )

    election_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("elections.id", ondelete="CASCADE"), index=True
    )
    office: Mapped[ResultOffice] = mapped_column(choice_type(ResultOffice, "result_office"))
    level: Mapped[ResultLevel] = mapped_column(choice_type(ResultLevel, "result_level"))
    # The codes as reported, without leading zeros, as the geography stores them.
    county_code: Mapped[str] = mapped_column(String(10), default="")
    constituency_code: Mapped[str] = mapped_column(String(10), default="")
    ward_code: Mapped[str] = mapped_column(String(10), default="")
    county_id: Mapped[uuid.UUID | None] = place_ref("counties")
    constituency_id: Mapped[uuid.UUID | None] = place_ref("constituencies")
    ward_id: Mapped[uuid.UUID | None] = place_ref("wards")
    area_name: Mapped[str] = mapped_column(String(100), default="")

    # Valid votes: the candidates' votes added up, as the source reports the contest total.
    total_votes: Mapped[int | None] = mapped_column(Integer, default=None)
    # Filled only where the source gives it (presidential rows).
    registered_voters: Mapped[int | None] = mapped_column(Integer, default=None)
    unopposed: Mapped[bool] = starts_false()
    # Figures that do not add up: kept for reading, left out of every target.
    excluded: Mapped[bool] = starts_false()
    note: Mapped[str] = mapped_column(Text, default="")
    source_ref: Mapped[str] = mapped_column(String(200), default="")

    election: Mapped["Election"] = relationship(back_populates="contests")
    candidates: Mapped[list["ContestCandidate"]] = relationship(
        back_populates="contest",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ContestCandidate.rank.asc().nulls_last()",
    )

    def __str__(self) -> str:
        return f"{self.election_id} {self.office} {self.area_name}"


class ContestCandidate(UUIDPrimaryKeyMixin, Base):
    """One candidate's votes in one contest; rank 1 won."""

    __tablename__ = "contest_candidates"
    __table_args__ = (CheckConstraint("votes IS NULL OR votes >= 0", name="votes_non_negative"),)

    contest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contests.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    party: Mapped[str] = mapped_column(String(100), default="")
    votes: Mapped[int | None] = mapped_column(Integer, default=None)
    rank: Mapped[int | None] = mapped_column(Integer, default=None)
    is_winner: Mapped[bool] = starts_false()

    contest: Mapped["Contest"] = relationship(back_populates="candidates")

    def __str__(self) -> str:
        return f"{self.name}: {self.votes if self.votes is not None else '-'}"
