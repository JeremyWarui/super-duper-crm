"""Vote targets: the win number per ward or per registration centre.

`votes_needed` is never taken from the client. It is recomputed from the
register and the projected turnout on every write.
"""

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, SessionDep, Writer, mobilizer_ward_id
from backend.api.scope import (
    limit_to_campaigns,
    require_own_ward,
    require_visible_campaign,
    visible_campaign_ids,
)
from backend.models import RegistrationCentre, Target, User, Ward
from backend.schemas.campaign import TargetCreate, TargetRead, TargetUpdate

router = APIRouter(prefix="/targets", tags=["targets"])

LOADED = (selectinload(Target.ward), selectinload(Target.registration_centre))


@router.get("/", response_model=list[TargetRead])
async def list_targets(
    session: SessionDep, user: CurrentUser, campaign: uuid.UUID | None = None
) -> list[Target]:
    statement = select(Target).options(*LOADED)
    if campaign is not None:
        statement = statement.where(Target.campaign_id == campaign)
    statement = limit_to_campaigns(
        statement, Target.campaign_id, await visible_campaign_ids(session, user)
    )
    own_ward = mobilizer_ward_id(user)
    if own_ward is not None:
        statement = statement.where(Target.ward_id == own_ward)
    statement = statement.join(Ward, Target.ward_id == Ward.id).order_by(Ward.name)
    return list((await session.execute(statement)).scalars().all())


@router.post("/", response_model=TargetRead, status_code=status.HTTP_201_CREATED)
async def create_target(
    payload: TargetCreate,
    session: SessionDep,
    user: CurrentUser,
    _: Writer,
) -> Target:
    await require_visible_campaign(session, user, payload.campaign)
    require_own_ward(user, payload.ward)

    target = Target(
        campaign_id=payload.campaign,
        ward_id=payload.ward,
        registration_centre_id=payload.registration_centre,
        projected_turnout_pct=payload.projected_turnout_pct,
        votes_committed=payload.votes_committed,
    )
    session.add(target)
    await _recompute(session, target)
    return await _reload(session, target.id)


@router.patch("/{target_id}/", response_model=TargetRead)
async def update_target(
    target_id: uuid.UUID,
    payload: TargetUpdate,
    session: SessionDep,
    user: CurrentUser,
    _: Writer,
) -> Target:
    """Change the turnout assumption or the votes committed; the goal follows."""
    target = await _visible_target(session, user, target_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(target, field, value)
    await _recompute(session, target)
    return await _reload(session, target.id)


@router.delete("/{target_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(
    target_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    _: Writer,
) -> Response:
    target = await _visible_target(session, user, target_id)
    await session.delete(target)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _visible_target(session: SessionDep, user: User, target_id: uuid.UUID) -> Target:
    target = (
        await session.execute(select(Target).where(Target.id == target_id).options(*LOADED))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such target.")
    await require_visible_campaign(session, user, target.campaign_id)
    require_own_ward(user, target.ward_id)
    return target


async def _recompute(session: SessionDep, target: Target) -> None:
    """Refresh the win number, with the rows it reads loaded first."""
    await session.flush()
    target.ward = await session.get(Ward, target.ward_id)
    if target.registration_centre_id is not None:
        target.registration_centre = await session.get(
            RegistrationCentre, target.registration_centre_id
        )
    target.recompute_win_number()
    await session.commit()


async def _reload(session: SessionDep, target_id: uuid.UUID) -> Target:
    return (
        await session.execute(select(Target).where(Target.id == target_id).options(*LOADED))
    ).scalar_one()
