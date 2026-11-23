"""A vote target: the share of the seat target one ward or centre is asked for."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import (
    Base,
    UUIDPrimaryKeyMixin,
    campaign_ref,
    choice_type,
    partial_unique,
    require_loaded,
    starts_false,
)
from backend.models.enums import TargetReliability, TurnoutScenario

if TYPE_CHECKING:
    from backend.models.campaign import Campaign
    from backend.models.geography import RegistrationCentre, Ward


def unit_key(ward_id: uuid.UUID, centre_id: uuid.UUID | None) -> tuple[uuid.UUID, uuid.UUID | None]:
    """The ward or centre a target, event or mobilizer covers."""
    return (ward_id, centre_id)


class Target(UUIDPrimaryKeyMixin, Base):
    """A vote goal for one ward, or for one registration centre inside it."""

    __tablename__ = "targets"
    __table_args__ = (
        partial_unique(
            "uq_targets_campaign_ward",
            "campaign_id",
            "ward_id",
            where="registration_centre_id IS NULL",
        ),
        partial_unique(
            "uq_targets_campaign_registration_centre",
            "campaign_id",
            "registration_centre_id",
            where="registration_centre_id IS NOT NULL",
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

    campaign_id: Mapped[uuid.UUID] = campaign_ref()
    ward_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="CASCADE"), index=True
    )
    registration_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("registration_centres.id", ondelete="CASCADE"),
        default=None,
        index=True,
    )

    # The seat's turnout the target was worked out on, in percent.
    projected_turnout_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    turnout_scenario: Mapped[TurnoutScenario] = mapped_column(
        choice_type(TurnoutScenario, "turnout_scenario"),
        default=TurnoutScenario.EXPECTED,
        server_default=TurnoutScenario.EXPECTED.value,
    )
    turnout_overridden: Mapped[bool] = starts_false()
    # This unit's share of the seat target: its share of the seat's 2022 valid votes.
    ward_weight: Mapped[Decimal | None] = mapped_column(Numeric(11, 10), default=None)
    reliability: Mapped[TargetReliability] = mapped_column(
        choice_type(TargetReliability, "target_reliability"),
        default=TargetReliability.PROXY,
        server_default=TargetReliability.PROXY.value,
    )
    # The unit's register when the target was last worked out; a register import leaves it.
    registered_voters: Mapped[int | None] = mapped_column(Integer, default=None)
    # Calculated, never typed in; the units' targets add up to the seat target.
    votes_needed: Mapped[int | None] = mapped_column(Integer, default=None)
    votes_committed: Mapped[int] = mapped_column(Integer, default=0)

    campaign: Mapped["Campaign"] = relationship(back_populates="targets")
    ward: Mapped["Ward"] = relationship(back_populates="targets")
    registration_centre: Mapped["RegistrationCentre | None"] = relationship(
        back_populates="targets"
    )

    def __str__(self) -> str:
        return f"{self.ward.name}: need {self.votes_needed or '-'}"

    def take_register(self) -> int | None:
        """Copy in the centre's roll, or the ward's for a ward target; needs it loaded."""
        if self.registration_centre_id is not None:
            require_loaded(self, "registration_centre")
            unit = self.registration_centre
        else:
            require_loaded(self, "ward")
            unit = self.ward
        self.registered_voters = unit.registered_voters if unit is not None else None
        return self.registered_voters

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
