"""The win number: how many votes this campaign must bank in one unit.

Three bugs in the Django original are fixed here:

1. The foreign key pointed at `"RegistrationCenter"`, a model that never
   existed - the class is spelled `RegistrationCentre`. That FK could not
   resolve, so the app could not start.
2. `compute_win_number` read `self.registered_voters`, which is not a field on
   Target. It is always `None`, so the method could never compute anything.
   Registered voters live on the ward or the registration centre; the property
   below resolves whichever one this target is scoped to.
3. The field was named `registration_center` here but `registration_centre` on
   Mobilizer and Event. Unified on the British spelling used everywhere else.
"""

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
    """50% + 1 of the projected votes cast.

    `floor(registered_voters * turnout_pct / 100 / 2) + 1`

    Returns None when either input is missing or zero - with nothing projected
    to be cast there is no number to beat. Decimal throughout, because this is
    money-shaped arithmetic and float rounding at the .5 boundary would move
    the answer by a whole vote.
    """
    if not registered_voters or not projected_turnout_pct:
        return None
    projected_cast = Decimal(registered_voters) * Decimal(projected_turnout_pct) / Decimal(100)
    return int(projected_cast // 2) + 1


class Target(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "targets"
    __table_args__ = (
        # One target per ward when the campaign targets at ward level.
        Index(
            "uq_targets_campaign_ward",
            "campaign_id",
            "ward_id",
            unique=True,
            postgresql_where=text("registration_centre_id IS NULL"),
            sqlite_where=text("registration_centre_id IS NULL"),
        ),
        # One per registration centre when it targets at centre level.
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
        """Voters in whichever unit this target is scoped to.

        A target with a registration centre is a centre-level target and counts
        that centre's roll; otherwise it counts the whole ward's. Requires the
        relevant relationship to be loaded.
        """
        if self.registration_centre_id is not None:
            require_loaded(self, "registration_centre")
            centre = self.registration_centre
            return centre.registered_voters if centre is not None else None
        require_loaded(self, "ward")
        return self.ward.registered_voters if self.ward is not None else None

    def recompute_win_number(self) -> int | None:
        """Recalculate `votes_needed` in place.

        Django's version took `save=True` and called `self.save()`. There is no
        equivalent here: the change is flushed with the rest of the session.
        """
        self.votes_needed = compute_win_number(self.registered_voters, self.projected_turnout_pct)
        return self.votes_needed

    @property
    def votes_remaining(self) -> int | None:
        if self.votes_needed is None:
            return None
        return max(self.votes_needed - self.votes_committed, 0)

    @property
    def progress_pct(self) -> float:
        if not self.votes_needed:
            return 0.0
        return round(self.votes_committed / self.votes_needed * 100, 1)
