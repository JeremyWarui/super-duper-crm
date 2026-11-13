"""Party volunteer profiles: officer moves, member-driven moves, and the public requests."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Select,
    String,
    Uuid,
    bindparam,
    case,
    cast,
    literal,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload

from backend.db.session import first_or_refuse, upsert
from backend.models import (
    Constituency,
    ContactMethod,
    PartyMember,
    PartyMemberStatus,
    Profession,
    User,
    VolunteerArea,
    VolunteerProfile,
    VolunteerStatus,
    Ward,
)
from backend.security import new_withdraw_code
from backend.services.audit import record_if
from backend.services.campaign_volunteers import (
    OFFICER_TARGETS,
    audit,
    check_move,
    write_status,
)
from backend.services.consent import VOLUNTEER_WORDING
from backend.services.errors import Refused, refuse_erased, refuse_own_record
from backend.services.register import PlaceFilters, in_place, page

V = VolunteerStatus


async def _fresh(session: AsyncSession, where) -> VolunteerProfile | None:
    """The profile matching `where`, read from the database rather than the session."""
    return await session.scalar(
        select(VolunteerProfile).where(where).execution_options(populate_existing=True)
    )


async def set_status(
    session: AsyncSession, profile: VolunteerProfile, to: VolunteerStatus, *, actor: User
) -> None:
    """An officer's or a campaign manager's move to active or inactive, audited.

    The caller commits.
    """
    refuse_own_record(actor, profile.member_id)
    old = profile.status
    if to not in OFFICER_TARGETS:
        raise Refused("An officer can only make a volunteer active or inactive.")
    check_move(old, to)
    if to is V.ACTIVE and profile.member_id is not None:
        # The lock makes a concurrent member move wait, or this wait for it.
        member_status = await session.scalar(
            select(PartyMember.status)
            .where(PartyMember.id == profile.member_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if member_status is not PartyMemberStatus.APPROVED:
            raise Refused("Only an approved member can be an active volunteer.")
    await write_status(session, profile, old, status=to)
    audit(session, profile, "volunteer.status", {"from": old.value, "to": to.value}, actor=actor)


def set_notes(
    session: AsyncSession, profile: VolunteerProfile, notes: str | None, *, actor: User
) -> None:
    """Replace the officer's availability notes; the audit never holds the text."""
    refuse_own_record(actor, profile.member_id)
    refuse_erased(profile)
    profile.availability_notes = notes
    audit(session, profile, "volunteer.notes", {}, actor=actor)


async def follow_member(
    session: AsyncSession, member: PartyMember, new_status: PartyMemberStatus
) -> None:
    """Carry a member's new status to their profile, audited as "system"; the caller commits.

    A withdrawn or rejected member withdraws the profile; a suspended member makes an active
    one inactive. Does nothing when the member has no profile.
    """
    for attempt in range(2):
        profile = await _fresh(session, VolunteerProfile.member_id == member.id)
        if profile is None:
            return
        old = profile.status
        if new_status in (PartyMemberStatus.WITHDRAWN, PartyMemberStatus.REJECTED):
            if old is V.WITHDRAWN:
                return
            to, values = V.WITHDRAWN, {"withdraw_code": None}
        elif new_status is PartyMemberStatus.SUSPENDED and old is V.ACTIVE:
            to, values = V.INACTIVE, {}
        else:
            return
        try:
            await write_status(session, profile, old, status=to, **values)
        except Refused:
            if attempt:
                raise
            continue
        audit(
            session,
            profile,
            "volunteer.status",
            {"from": old.value, "to": to.value},
            actor_name="system",
        )
        return


def split_name(full_name: str) -> tuple[str, str]:
    """The first word, and the rest."""
    first, _, rest = full_name.strip().partition(" ")
    return first[:75], rest.strip()[:75]


async def apply_part(
    session: AsyncSession, member_id: uuid.UUID, join: dict, applies: bool
) -> None:
    """Create or refresh the member's profile from a queued join's volunteer part, when `applies`.

    `join` is the queued join's payload. `applies` holds only when the join added or re-pended
    the member, so a join with someone else's phone never touches their profile. Runs the same
    statements whatever the register holds.
    """
    part = join["volunteer"]
    if "surname" in join:
        first_name, last_name = join["first_name"][:75], join["surname"][:75]
    else:
        first_name, last_name = split_name(join["full_name"])
    centre = join.get("registration_centre_id")
    now = datetime.now(UTC)
    values = {
        "first_name": first_name,
        "last_name": last_name,
        "phone": join["phone"],
        "email": join["email"],
        "ward_id": uuid.UUID(join["ward_id"]),
        "registration_centre_id": uuid.UUID(centre) if centre else None,
        "profession": Profession(part["profession"]) if "profession" in part else None,
        "profession_other": part.get("profession_other", ""),
        "interests": [VolunteerArea(a).value for a in part.get("areas", [])],
        "interest_other": part.get("area_other", ""),
        "preferred_contact": ContactMethod(part["preferred_contact"]),
        "consent_wording": VOLUNTEER_WORDING,
        "consent_at": datetime.fromisoformat(part["consent_at"]),
        "withdraw_code": part["code"],
        "updated_at": now,
    }
    old = (
        await session.execute(
            select(VolunteerProfile.id, VolunteerProfile.status)
            .where(VolunteerProfile.member_id == member_id)
            .with_for_update()
        )
    ).first()
    revived = case(
        (
            VolunteerProfile.status == V.WITHDRAWN,
            literal(V.INTERESTED, VolunteerProfile.status.type),
        ),
        else_=VolunteerProfile.status,
    )
    new_id = uuid.uuid4()
    columns = VolunteerProfile.__table__.c
    row = {
        "id": new_id,
        "member_id": member_id,
        "status": V.INTERESTED,
        "created_at": now,
        **values,
    }
    await session.execute(
        upsert(session, VolunteerProfile)
        .from_select(
            list(row),
            select(*(literal(v, columns[k].type).label(k) for k, v in row.items())).where(
                literal(applies, Boolean)
            ),
        )
        .on_conflict_do_update(
            index_elements=["member_id"], set_={**values, "status": revived, "erased_at": None}
        )
    )
    to = V.INTERESTED if old is None or old.status is V.WITHDRAWN else old.status
    await record_if(
        session,
        applies,
        actor_name="public",
        action="volunteer.interest",
        subject_type="volunteer_profile",
        subject_id=old.id if old else new_id,
        detail={"from": old.status.value if old else None, "to": to.value},
    )


async def _withdraw_where(
    session: AsyncSession, where, applies: bool, *, actor_name: str, action: str
) -> None:
    """Withdraw the profile matching `where` when `applies`, with the same statements either way."""
    old = (
        await session.execute(
            select(VolunteerProfile.id, VolunteerProfile.status).where(where).with_for_update()
        )
    ).first()
    changed = await session.execute(
        update(VolunteerProfile)
        .where(where, VolunteerProfile.status != V.WITHDRAWN, literal(applies, Boolean))
        .values(status=V.WITHDRAWN, withdraw_code=None, updated_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    await record_if(
        session,
        changed.rowcount == 1,
        actor_name=actor_name,
        action=action,
        subject_type="volunteer_profile",
        subject_id=old.id if old else None,
        detail={"from": old.status.value if old else None, "to": V.WITHDRAWN.value},
    )


async def follow_withdrawal(
    session: AsyncSession, member_id: uuid.UUID | None, withdrawn: bool
) -> None:
    """Withdraw the profile of a member the public link just withdrew, audited as "system"."""
    await _withdraw_where(
        session,
        VolunteerProfile.member_id == bindparam("member_id", member_id, type_=Uuid),
        withdrawn,
        actor_name="system",
        action="volunteer.status",
    )


async def withdraw_by_code(session: AsyncSession, code: str) -> None:
    """The volunteer's own withdrawal through their link; the link works once."""
    await _withdraw_where(
        session,
        VolunteerProfile.withdraw_code == code,
        True,
        actor_name="public",
        action="volunteer.withdraw",
    )


@dataclass(frozen=True)
class VolunteerFilters(PlaceFilters):
    status: VolunteerStatus | None = None
    area: VolunteerArea | None = None


def _query(filters: VolunteerFilters) -> Select:
    statement = (
        select(VolunteerProfile)
        .join(VolunteerProfile.member)
        .join(PartyMember.ward)
        .join(Ward.constituency)
        .options(
            contains_eager(VolunteerProfile.member)
            .contains_eager(PartyMember.ward)
            .contains_eager(Ward.constituency)
            .joinedload(Constituency.county),
            joinedload(VolunteerProfile.registration_centre),
        )
        .where(VolunteerProfile.campaign_id.is_(None))
    )
    statement = in_place(statement, filters)
    if filters.status is not None:
        statement = statement.where(VolunteerProfile.status == filters.status)
    if filters.area is not None:
        # The JSON list as text holds each value quoted, so "other" matches only that value.
        statement = statement.where(
            cast(VolunteerProfile.interests, String).contains(
                f'"{filters.area.value}"', autoescape=True
            )
        )
    return statement.order_by(VolunteerProfile.created_at.desc(), VolunteerProfile.id)


async def volunteers(
    session: AsyncSession, filters: VolunteerFilters, limit: int, offset: int
) -> tuple[int, list[VolunteerProfile]]:
    """One page of the volunteer register, newest first, and the count of all that match."""
    return await page(session, _query(filters), VolunteerProfile.id, limit, offset)


async def export_rows(session: AsyncSession, filters: VolunteerFilters) -> list[VolunteerProfile]:
    """Every volunteer matching the filters, newest first."""
    return list((await session.scalars(_query(filters))).unique())


async def get_volunteer(session: AsyncSession, volunteer_id: uuid.UUID) -> VolunteerProfile:
    """The profile with its member and places loaded; NotFound when missing."""
    return await first_or_refuse(
        session,
        _query(VolunteerFilters())
        .where(VolunteerProfile.id == volunteer_id)
        .execution_options(populate_existing=True),
        "volunteer",
    )


OWN_FIELDS = ("profession", "profession_other", "interests", "interest_other", "preferred_contact")


async def own_update(
    session: AsyncSession, member: PartyMember, part: dict, *, actor: User
) -> None:
    """A member's own volunteer details: changed, or a new or withdrawn profile made interested.

    `part` is a `VolunteerPart` dump. The caller commits.
    """
    values = {
        "profession": Profession(part["profession"]),
        "profession_other": part["profession_other"],
        "interests": [VolunteerArea(a).value for a in part["areas"]],
        "interest_other": part["area_other"],
        "preferred_contact": ContactMethod(part["preferred_contact"]),
    }
    profile = await _fresh(session, VolunteerProfile.member_id == member.id)
    if profile is not None and profile.status is not V.WITHDRAWN:
        changed = [name for name in OWN_FIELDS if getattr(profile, name) != values[name]]
        for name, value in values.items():
            setattr(profile, name, value)
        audit(session, profile, "volunteer.self_update", {"fields": changed}, actor=actor)
        return
    first_name, last_name = split_name(member.full_name)
    renewed = {
        **values,
        "first_name": member.first_name or first_name,
        "last_name": last_name,
        "phone": member.phone,
        "email": member.email,
        "ward_id": member.ward_id,
        "registration_centre_id": member.registration_centre_id,
        "consent_wording": VOLUNTEER_WORDING,
        "consent_at": datetime.now(UTC),
        "withdraw_code": new_withdraw_code(),
        "erased_at": None,
    }
    if profile is None:
        profile = VolunteerProfile(member_id=member.id, status=V.INTERESTED, **renewed)
        session.add(profile)
        await session.flush()
        old = None
    else:
        await write_status(session, profile, V.WITHDRAWN, status=V.INTERESTED, **renewed)
        old = V.WITHDRAWN.value
    audit(
        session, profile, "volunteer.status", {"from": old, "to": V.INTERESTED.value}, actor=actor
    )


async def own_stop(session: AsyncSession, member: PartyMember, *, actor: User) -> None:
    """A member stops volunteering and keeps their membership; the caller commits."""
    profile = await _fresh(session, VolunteerProfile.member_id == member.id)
    if profile is None or profile.status is V.WITHDRAWN:
        return
    old = profile.status
    await write_status(session, profile, old, status=V.WITHDRAWN, withdraw_code=None)
    audit(
        session,
        profile,
        "volunteer.status",
        {"from": old.value, "to": V.WITHDRAWN.value},
        actor=actor,
    )
