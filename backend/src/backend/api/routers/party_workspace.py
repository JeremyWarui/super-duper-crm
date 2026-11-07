"""The party's coordination workspace: the superuser creates it and its first Workspace
Manager; its coordinators read the member register for their area and hold recruitment links.

Mounted only in a party installation.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from backend.api.deps import AdminUser, CurrentUser, SessionDep
from backend.api.install import PartyOnlyRoute
from backend.api.scope import area_ids
from backend.models import CampaignMember, User, UserRole
from backend.schemas.party_workspace import (
    AreaMember,
    AreaMembers,
    PartyWorkspaceCreate,
    PartyWorkspaceCreated,
    PartyWorkspaceManager,
    PartyWorkspaceRead,
    Recruitment,
)
from backend.schemas.team import ManagerCreated
from backend.services import party_workspace, team
from backend.services.errors import NotFound

router = APIRouter(prefix="/party/workspace", tags=["party workspace"], route_class=PartyOnlyRoute)


async def _coordinator(user: CurrentUser, session: SessionDep) -> CampaignMember:
    """The caller's coordinator place on the party workspace; 404 for anyone else."""
    member = await party_workspace.coordinator(session, user)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return member


Coordinator = Annotated[CampaignMember, Depends(_coordinator)]


@router.get("/", response_model=PartyWorkspaceRead)
async def read_workspace(session: SessionDep, _: AdminUser) -> PartyWorkspaceRead:
    found = await party_workspace.workspace(session)
    if found is None:
        return PartyWorkspaceRead()
    managers = await session.scalars(
        select(User.username)
        .join(CampaignMember, CampaignMember.user_id == User.id)
        .where(CampaignMember.campaign_id == found.id, CampaignMember.role == UserRole.MANAGER)
    )
    return PartyWorkspaceRead(id=found.id, title=found.title, managers=list(managers))


@router.post("/", response_model=PartyWorkspaceCreated, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: PartyWorkspaceCreate, session: SessionDep, user: AdminUser
) -> PartyWorkspaceCreated:
    """Create the party workspace and its Workspace Manager, who is sent an invite link."""
    campaign, summary, manager, invite = await party_workspace.create(
        session, actor=user, manager=payload.manager.model_dump()
    )
    return PartyWorkspaceCreated(
        id=campaign.id,
        title=campaign.title,
        units=summary.units,
        username=manager.username,
        invite=invite,
    )


@router.post("/manager/", response_model=ManagerCreated)
async def replace_manager(
    payload: PartyWorkspaceManager, session: SessionDep, user: AdminUser
) -> ManagerCreated:
    """Replace the Workspace Manager: the sitting one is turned off and signed out, and the new
    login is sent an invite link."""
    found = await party_workspace.workspace(session)
    if found is None:
        raise NotFound("The party has no workspace yet.")
    created, invite, replaced = await team.set_manager(
        session, found, payload.manager.model_dump(), replace=True, actor=user
    )
    return ManagerCreated(
        id=created.id,
        username=created.username,
        full_name=created.full_name,
        invite=invite,
        replaced=replaced,
    )


@router.get("/members/", response_model=AreaMembers)
async def area_members(
    member: Coordinator,
    user: CurrentUser,
    session: SessionDep,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
) -> AreaMembers:
    """Party members living in the coordinator's area, a page at a time; every read is audited."""
    total, rows = await party_workspace.members_in_area(
        session, member, await area_ids(session, user), page, actor=user
    )
    return AreaMembers(
        total=total,
        page=page,
        page_size=party_workspace.PAGE_SIZE,
        members=[
            AreaMember(
                id=m.id,
                full_name=m.full_name,
                phone=m.phone,
                status=m.status,
                ward=m.ward_id,
                ward_name=m.ward.name,
                registration_centre=m.registration_centre_id,
                registration_centre_name=m.registration_centre.name
                if m.registration_centre
                else "",
            )
            for m in rows
        ],
    )


@router.get("/recruitment/", response_model=Recruitment)
async def read_recruitment(
    member: Coordinator, user: CurrentUser, session: SessionDep
) -> Recruitment:
    """The coordinator's recruitment code, made on first ask, and their applicants by status."""
    code, counts = await party_workspace.recruitment(session, member, replace=False, actor=user)
    return Recruitment(code=code, by_status=counts)


@router.post("/recruitment/", response_model=Recruitment)
async def replace_recruitment(
    member: Coordinator, user: CurrentUser, session: SessionDep
) -> Recruitment:
    """Retire the coordinator's code and issue a new one; the old link stops recruiting."""
    code, counts = await party_workspace.recruitment(session, member, replace=True, actor=user)
    return Recruitment(code=code, by_status=counts)
