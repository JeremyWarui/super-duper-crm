"""Vote targets; `votes_needed` is calculated from past results, never taken from the client."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.api.deps import SessionDep, require
from backend.api.scope import (
    all_rows,
    load,
    require_place,
    require_visible,
    require_visible_campaign,
    scoped,
)
from backend.models import OperationalGrain, Target, User, Ward
from backend.schemas.campaign import (
    SetupSummary,
    TargetCreate,
    TargetRead,
    TargetRefresh,
    TargetUpdate,
)
from backend.services.errors import Refused
from backend.services.geography import within
from backend.services.targets import generate_targets, refresh_targets

router = APIRouter(prefix="/targets", tags=["targets"])

LOADED = (
    selectinload(Target.ward).selectinload(Ward.constituency),
    selectinload(Target.registration_centre),
)
Reader = Annotated[User, Depends(require("targets.read"))]
Writer = Annotated[User, Depends(require("targets.write"))]
TARGET_TAKEN = "That unit already has a target."


@router.get("/", response_model=list[TargetRead])
async def list_targets(
    session: SessionDep,
    user: Reader,
    campaign: uuid.UUID | None = None,
    county: uuid.UUID | None = None,
    constituency: uuid.UUID | None = None,
) -> list[Target]:
    """The caller's targets by ward name, only those in `county` or `constituency` when given."""
    statement = await scoped(
        session, user, select(Target).options(*LOADED), Target, campaign, "targets.read"
    )
    statement = within(statement, Target.ward_id, county=county, constituency=constituency)
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
    campaign = await require_place(
        session, user, "targets.write", payload.campaign, payload.ward, payload.registration_centre
    )
    if campaign.operational_grain is OperationalGrain.WARD and payload.registration_centre:
        raise Refused(f"This race ({campaign.seat_label}) sets targets per ward, not per centre.")
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
        raise Refused(TARGET_TAKEN)

    target = Target(
        campaign_id=payload.campaign,
        ward_id=payload.ward,
        registration_centre_id=payload.registration_centre,
        votes_committed=payload.votes_committed,
    )
    session.add(target)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise Refused(TARGET_TAKEN) from None
    await session.flush()
    await generate_targets(session, campaign)
    await session.commit()
    return await load(session, Target, target.id, LOADED)


@router.patch("/{target_id}/", response_model=TargetRead)
async def update_target(
    target_id: uuid.UUID, payload: TargetUpdate, session: SessionDep, user: Writer
) -> Target:
    """Change the votes committed; the target stays as calculated."""
    target = await require_visible(
        session, user, Target, target_id, "target", "targets.write", LOADED
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, field, value)
    await session.commit()
    return await load(session, Target, target.id, LOADED)


@router.delete("/{target_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(target_id: uuid.UUID, session: SessionDep, user: Writer) -> None:
    target = await require_visible(session, user, Target, target_id, "target", "targets.write")
    await session.delete(target)
    await session.commit()
