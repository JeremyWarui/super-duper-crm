"""The seat's target before the campaign exists (AO-R8 setup step 5): its past results, share,
turnout scenarios and the split to wards, worked out exactly as `generate_targets` saves them."""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Seat
from backend.services.campaigns import campaign_for
from backend.services.targets import plan_targets
from backend.services.win_model import as_decimal


def _pct(value) -> str:  # type: ignore[no-untyped-def]
    return str(as_decimal(value * 100, 2))


async def preview(
    session: AsyncSession,
    *,
    seat: Seat,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
    ward: uuid.UUID | None = None,
    election_date: date | None = None,
) -> dict:
    """What setup would save for this seat, as figures to show; reads only."""
    campaign = await campaign_for(
        session,
        title="Preview",
        seat=seat,
        election_date=election_date,
        county=county,
        constituency=constituency,
        ward=ward,
    )
    plan = await plan_targets(session, campaign)
    model, history = plan.model, plan.history
    units = []
    for unit_ward, centre in plan.units:
        key = (unit_ward.id, centre.id if centre is not None else None)
        units.append(
            {
                "name": centre.name if centre is not None else unit_ward.name,
                "weight_pct": _pct(plan.weight(key)),
                "target": plan.shares[key],
            }
        )
    units.sort(key=lambda u: u["target"], reverse=True)
    return {
        "seat": seat.label,
        "registered_voters": history.register,
        "results": [
            {
                "year": year,
                "valid_votes": result.valid,
                "winner_share_pct": _pct(result.share) if result.share is not None else None,
            }
            for year, result in sorted(history.results.items())
        ],
        "share_pct": _pct(model.share),
        "typical_pct": _pct(model.typical) if model.typical is not None else None,
        "reliability": model.reliability,
        "two_candidate": model.two_candidate,
        "turnout_pct": _pct(model.turnout),
        "scenarios": [
            {
                "scenario": p.scenario,
                "turnout_pct": _pct(p.turnout),
                "projected": p.projected,
                "competitive": p.competitive,
                "majority": p.majority,
                "target": p.target,
            }
            for p in model.scenarios.values()
        ],
        "seat_target": plan.seat_target,
        "units": units,
        "note": plan.note,
    }
