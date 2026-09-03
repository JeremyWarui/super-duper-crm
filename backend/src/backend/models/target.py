"""The win number: how many votes a campaign needs in one ward or centre."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, UUIDPrimaryKeyMixin, require_loaded

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.geography import RegistrationCentre, Ward


def compute_win_number(
    registered_voters: int | None,
    projected_turnout_pct: Decimal | None,
) -> int | None:
    """Half the projected votes cast, plus one.

    `floor(registered_voters * turnout_pct / 100 / 2) + 1`, or None when nothing
    is projected to be cast. Decimal rather than float, because float rounding
    at the halfway point shifts the answer by a whole vote.
    """
    if not registered_voters or not projected_turnout_pct:
        return None
    projected_cast = Decimal(registered_voters) * Decimal(projected_turnout_pct) / Decimal(100)
    return int(projected_cast // 2) + 1


class Target(UUIDPrimaryKeyMixin, Base):
    """A vote goal for one ward, or for one registration centre inside it."""

    __tablename__ = "targets"
    __table_args__ = (
        # A campaign gets one ward-level target per ward...
        Index(
            "uq_targets_campaign_ward",
            "campaign_id",
            "ward_id",
            unique=True,
            postgresql_where=text("registration_centre_id IS NULL"),
            sqlite_where=text("registration_centre_id IS NULL"),
        ),
        # ...and one target per registration centre. The WHERE clauses keep
        # these two rules from colliding with each other.
        Index(
            "uq_targets_campaign_registration_centre",
            "campaign_id",
            "registration_centre_id",
            unique=True,
            postgresql_where=text("registration_centre_id IS NOT NULL"),
            sqlite_where=text("registration_centre_id IS NOT NULL"),
        ),
        CheckConstraint(
            "votes_needed IS NULL OR votes_needed >= 0", name="votes_needed_non_negative"
        ),
        CheckConstraint("votes_committed >= 0", name="votes_committed_non_negative"),
        CheckConstraint(
            "projected_turnout_pct IS NULL "
            "OR (projected_turnout_pct >= 0 AND projected_turnout_pct <= 100)",
            name="projected_turnout_pct_range",
        ),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    ward_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="CASCADE"), index=True
    )
    # Set for a centre-level target, empty for a ward-level one.
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("registration_centres.id", ondelete="CASCADE"),
        default=None,
        index=True,
    )

    projected_turnout_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    votes_needed: Mapped[int | None] = mapped_column(Integer, default=None)
    votes_committed: Mapped[int] = mapped_column(Integer, default=0)

    campaign: Mapped["Campaign"] = relationship(back_populates="targets")
    ward: Mapped["Ward"] = relationship(back_populates="targets")
    registration_centre: Mapped["RegistrationCentre | None"] = relationship(
        back_populates="targets"
    )

    def __str__(self) -> str:
        return f"{self.ward.name}: need {self.votes_needed or '-'}"

    @property
    def registered_voters(self) -> int | None:
        """Voters on the roll of whichever unit this target covers.

        The centre for a centre-level target, otherwise the whole ward. That
        relationship must be loaded.
        """
        if self.registration_centre_id is not None:
            require_loaded(self, "registration_centre")
            centre = self.registration_centre
            return centre.registered_voters if centre is not None else None
        require_loaded(self, "ward")
        return self.ward.registered_voters if self.ward is not None else None

    def recompute_win_number(self) -> int | None:
        """Recalculate `votes_needed`. Saved when the session is committed."""
        self.votes_needed = compute_win_number(self.registered_voters, self.projected_turnout_pct)
        return self.votes_needed

    @property
    def votes_remaining(self) -> int | None:
        """How many more votes to commit, never below zero."""
        if self.votes_needed is None:
            return None
        return max(self.votes_needed - self.votes_committed, 0)

    @property
    def progress_pct(self) -> float:
        """Votes committed as a percentage of votes needed."""
        if not self.votes_needed:
            return 0.0
        return round(self.votes_committed / self.votes_needed * 100, 1)
