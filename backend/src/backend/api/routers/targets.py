"""Vote targets; `votes_needed` is recomputed on every write, never taken from the client."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.api.deps import SessionDep, require
from backend.api.scope import (
    all_rows,
    load,
    require_centre_in_ward_race,
    require_in_area,
    require_visible,
    require_visible_campaign,
    require_ward_in_campaign,
    scoped,
)
from backend.models import OperationalGrain, RegistrationCentre, Target, User, Ward
from backend.schemas.campaign import (
    SetupSummary,
    TargetCreate,
    TargetRead,
    TargetRefresh,
    TargetUpdate,
)
from backend.services.targets import refresh_targets

router = APIRouter(prefix="/targets", tags=["targets"])

LOADED = (selectinload(Target.ward), selectinload(Target.registration_centre))
Reader = Annotated[User, Depends(require("targets.read"))]
Writer = Annotated[User, Depends(require("targets.write"))]


@router.get("/", response_model=list[TargetRead])
async def list_targets(
    session: SessionDep, user: Reader, campaign: uuid.UUID | None = None
) -> list[Target]:
    statement = await scoped(
        session, user, select(Target).options(*LOADED), Target, campaign, "targets.read"
    )
    return await all_rows(
        session, statement.join(Ward, Target.ward_id == Ward.id).order_by(Ward.name)
    )


@router.post("/refresh/", response_model=SetupSummary)
async def refresh(
    payload: TargetRefresh,
    session: SessionDep,
    user: Annotated[User, Depends(require("targets.write", whole=True))],
) -> SetupSummary:
    """Recompute the campaign's targets from the current voter register."""
    campaign = await require_visible_campaign(session, user, payload.campaign)
    return await refresh_targets(session, campaign, actor=user)


@router.post("/", response_model=TargetRead, status_code=status.HTTP_201_CREATED)
async def create_target(payload: TargetCreate, session: SessionDep, user: Writer) -> Target:
    campaign = await require_visible_campaign(session, user, payload.campaign)
    await require_in_area(session, user, "targets.write", payload.ward, payload.registration_centre)
    await require_ward_in_campaign(session, campaign, payload.ward, payload.registration_centre)
    await require_centre_in_ward_race(session, campaign, payload.ward, payload.registration_centre)
    if campaign.operational_grain is OperationalGrain.WARD and payload.registration_centre:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"This race ({campaign.seat_label}) sets targets per ward, not per centre.",
        )
    taken = set(
        (
            await session.execute(
                select(Target.registration_centre_id).where(
                    Target.campaign_id == campaign.id, Target.ward_id == payload.ward
                )
            )
        ).scalars()
    )
    if payload.registration_centre in taken:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That unit already has a target.")

    target = Target(
        campaign_id=payload.campaign,
        ward_id=payload.ward,
        registration_centre_id=payload.registration_centre,
        projected_turnout_pct=payload.projected_turnout_pct,
        votes_committed=payload.votes_committed,
    )
    session.add(target)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "That unit already has a target."
        ) from None
    return await _saved(session, target, new=True)


@router.patch("/{target_id}/", response_model=TargetRead)
async def update_target(
    target_id: uuid.UUID, payload: TargetUpdate, session: SessionDep, user: Writer
) -> Target:
    """Change the turnout or the votes committed; the goal follows."""
    target = await require_visible(
        session, user, Target, target_id, "target", "targets.write", LOADED
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, field, value)
    return await _saved(session, target)


@router.delete("/{target_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(target_id: uuid.UUID, session: SessionDep, user: Writer) -> Response:
    target = await require_visible(session, user, Target, target_id, "target", "targets.write")
    await session.delete(target)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _saved(session: SessionDep, target: Target, *, new: bool = False) -> Target:
    """Recompute the win number, commit, and read the target back; a new target takes the
    current register, an existing one keeps the one it was refreshed on."""
    await session.flush()
    target.ward = await session.get(Ward, target.ward_id)
    if target.registration_centre_id is not None:
        target.registration_centre = await session.get(
            RegistrationCentre, target.registration_centre_id
        )
    if new:
        target.take_register()
    target.recompute_win_number()
    await session.commit()
    return await load(session, Target, target.id, LOADED)
