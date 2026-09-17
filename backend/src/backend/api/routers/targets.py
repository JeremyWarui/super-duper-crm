"""Vote targets; `votes_needed` is recomputed on every write, never taken from the client."""

import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, Writer
from backend.api.scope import (
    all_rows,
    load,
    require_own_ward,
    require_visible,
    require_visible_campaign,
    require_ward_in_campaign,
    scoped,
)
from backend.models import RegistrationCentre, Target, Ward
from backend.schemas.campaign import TargetCreate, TargetRead, TargetUpdate

router = APIRouter(prefix="/targets", tags=["targets"])

LOADED = (selectinload(Target.ward), selectinload(Target.registration_centre))


@router.get("/", response_model=list[TargetRead])
async def list_targets(
    session: SessionDep, user: CurrentUser, campaign: uuid.UUID | None = None
) -> list[Target]:
    statement = await scoped(session, user, select(Target).options(*LOADED), Target, campaign)
    return await all_rows(
        session, statement.join(Ward, Target.ward_id == Ward.id).order_by(Ward.name)
    )


@router.post("/", response_model=TargetRead, status_code=status.HTTP_201_CREATED)
async def create_target(payload: TargetCreate, session: SessionDep, user: Writer) -> Target:
    campaign = await require_visible_campaign(session, user, payload.campaign)
    require_own_ward(user, payload.ward)
    await require_ward_in_campaign(session, campaign, payload.ward, payload.registration_centre)

    target = Target(
        campaign_id=payload.campaign,
        ward_id=payload.ward,
        registration_centre_id=payload.registration_centre,
        projected_turnout_pct=payload.projected_turnout_pct,
        votes_committed=payload.votes_committed,
    )
    session.add(target)
    return await _saved(session, target)


@router.patch("/{target_id}/", response_model=TargetRead)
async def update_target(
    target_id: uuid.UUID, payload: TargetUpdate, session: SessionDep, user: Writer
) -> Target:
    """Change the turnout or the votes committed; the goal follows."""
    target = await require_visible(session, user, Target, target_id, "target", LOADED)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, field, value)
    return await _saved(session, target)


@router.delete("/{target_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(target_id: uuid.UUID, session: SessionDep, user: Writer) -> Response:
    target = await require_visible(session, user, Target, target_id, "target")
    await session.delete(target)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _saved(session: SessionDep, target: Target) -> Target:
    """Recompute the win number, commit, and read the target back."""
    await session.flush()
    target.ward = await session.get(Ward, target.ward_id)
    if target.registration_centre_id is not None:
        target.registration_centre = await session.get(
            RegistrationCentre, target.registration_centre_id
        )
    target.recompute_win_number()
    await session.commit()
    return await load(session, Target, target.id, LOADED)
