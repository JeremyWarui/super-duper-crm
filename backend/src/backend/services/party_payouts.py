"""The finance officer's payments to agents, volunteers, members and staff."""

import uuid

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Aspirant,
    AspirantStatus,
    PartyMember,
    PartyMemberStatus,
    PartyPayment,
    PaymentStatus,
    RegistrationCentre,
    User,
    VolunteerProfile,
    VolunteerStatus,
)
from backend.schemas.party_payment import (
    CampaignOption,
    PartyPaymentCreate,
    PayeeOption,
    SpendReport,
    SpendRow,
)
from backend.services.audit import record
from backend.services.errors import NotFound, Refused
from backend.services.sms import normalise_phone

OWED = (PaymentStatus.SCHEDULED, PaymentStatus.SENDING, PaymentStatus.FAILED)
PAYEES_SHOWN = 20
LIVE_VOLUNTEER = (VolunteerStatus.INTERESTED, VolunteerStatus.ACTIVE)


def _label(aspirant: Aspirant) -> str:
    place = aspirant.ward or aspirant.constituency or aspirant.county
    return " · ".join(
        p for p in (aspirant.member.full_name, aspirant.seat.label, place and place.name) if p
    )


async def _approved_aspirants(session: AsyncSession, *where) -> list[Aspirant]:
    return list(
        await session.scalars(
            select(Aspirant)
            .where(Aspirant.status == AspirantStatus.APPROVED, *where)
            .options(
                selectinload(Aspirant.member),
                selectinload(Aspirant.ward),
                selectinload(Aspirant.constituency),
                selectinload(Aspirant.county),
            )
        )
    )


async def campaigns(session: AsyncSession) -> list[CampaignOption]:
    """Approved aspirants a payment can be for, by label."""
    options = [
        CampaignOption(aspirant=a.id, label=_label(a)) for a in await _approved_aspirants(session)
    ]
    return sorted(options, key=lambda o: o.label.lower())


async def payees(session: AsyncSession, q: str) -> list[PayeeOption]:
    """Approved members and live party volunteers whose name or phone matches `q`."""
    needle = f"%{q.strip().lower()}%"
    members = await session.execute(
        select(PartyMember, RegistrationCentre.name)
        .outerjoin(RegistrationCentre, RegistrationCentre.id == PartyMember.registration_centre_id)
        .where(
            PartyMember.status == PartyMemberStatus.APPROVED,
            or_(func.lower(PartyMember.full_name).like(needle), PartyMember.phone.like(needle)),
        )
        .order_by(PartyMember.full_name)
        .limit(PAYEES_SHOWN)
    )
    volunteers = await session.execute(
        select(VolunteerProfile, RegistrationCentre.name)
        .outerjoin(
            RegistrationCentre, RegistrationCentre.id == VolunteerProfile.registration_centre_id
        )
        .where(
            VolunteerProfile.campaign_id.is_(None),
            VolunteerProfile.status.in_(LIVE_VOLUNTEER),
            or_(
                func.lower(VolunteerProfile.first_name + " " + VolunteerProfile.last_name).like(
                    needle
                ),
                VolunteerProfile.phone.like(needle),
            ),
        )
        .order_by(VolunteerProfile.first_name, VolunteerProfile.last_name)
        .limit(PAYEES_SHOWN)
    )
    return [
        PayeeOption(
            source="member", id=m.id, name=m.full_name, phone=m.phone, polling_station=c or ""
        )
        for m, c in members
    ] + [
        PayeeOption(
            source="volunteer",
            id=v.id,
            name=f"{v.first_name} {v.last_name}",
            phone=v.phone,
            polling_station=c or "",
        )
        for v, c in volunteers
    ]


async def _centre_name(session: AsyncSession, centre_id: uuid.UUID | None) -> str:
    if centre_id is None:
        return ""
    name = await session.scalar(
        select(RegistrationCentre.name).where(RegistrationCentre.id == centre_id)
    )
    if name is None:
        raise NotFound("No such polling station.")
    return name


async def schedule(
    session: AsyncSession, payload: PartyPaymentCreate, *, actor: User
) -> PartyPayment:
    payment = PartyPayment(
        payee_kind=payload.payee_kind,
        amount_kes=payload.amount_kes,
        purpose=payload.purpose,
        created_by_id=actor.id,
    )
    if payload.member:
        member = await session.get(PartyMember, payload.member)
        if member is None or member.status is not PartyMemberStatus.APPROVED:
            raise NotFound("No such approved party member.")
        payment.member_id = member.id
        payment.recipient_name, phone = member.full_name, member.phone
        centre = member.registration_centre_id
    elif payload.volunteer:
        volunteer = await session.get(VolunteerProfile, payload.volunteer)
        if (
            volunteer is None
            or volunteer.campaign_id is not None
            or volunteer.status not in LIVE_VOLUNTEER
        ):
            raise NotFound("No such party volunteer.")
        payment.volunteer_id = volunteer.id
        payment.recipient_name = f"{volunteer.first_name} {volunteer.last_name}"
        phone, centre = volunteer.phone, volunteer.registration_centre_id
    else:
        payment.recipient_name, phone, centre = payload.name, payload.phone, payload.centre
    payment.recipient_phone = normalise_phone(phone) or ""
    if not payment.recipient_phone:
        raise Refused(f"{payment.recipient_name} has no usable phone number.")
    payment.registration_centre_id = centre
    payment.polling_station = await _centre_name(session, centre)
    if payload.aspirant:
        found = await _approved_aspirants(session, Aspirant.id == payload.aspirant)
        if not found:
            raise NotFound("No such approved aspirant.")
        payment.aspirant_id, payment.campaign_label = found[0].id, _label(found[0])
    session.add(payment)
    await session.flush()
    record(
        session,
        actor=actor,
        action="finance.payout.schedule",
        subject_type="party_payment",
        subject_id=payment.id,
        detail={"amount_kes": payment.amount_kes, "payee_kind": payment.payee_kind.value},
    )
    await session.commit()
    return payment


async def current_phone(session: AsyncSession, payment: PartyPayment) -> str | None:
    """The payee's number in the register now; the scheduled one when typed in by hand."""
    if payment.member_id:
        row = await session.get(PartyMember, payment.member_id)
    elif payment.volunteer_id:
        row = await session.get(VolunteerProfile, payment.volunteer_id)
    else:
        return normalise_phone(payment.recipient_phone)
    return (
        normalise_phone(row.phone) if row is not None else normalise_phone(payment.recipient_phone)
    )


async def spend(session: AsyncSession) -> SpendReport:
    """Paid and still-owed money per campaign; cancelled payments count nowhere."""
    paid = func.coalesce(
        func.sum(case((PartyPayment.status == PaymentStatus.PAID, PartyPayment.amount_kes))), 0
    )
    owed = func.coalesce(
        func.sum(case((PartyPayment.status.in_(OWED), PartyPayment.amount_kes))), 0
    )
    # One row per aspirant whatever its label became; a deleted aspirant's payments by label.
    orphan_label = case((PartyPayment.aspirant_id.is_(None), PartyPayment.campaign_label), else_="")
    result = await session.execute(
        select(
            PartyPayment.aspirant_id,
            func.max(PartyPayment.campaign_label),
            paid,
            owed,
            func.count(),
        )
        .where(PartyPayment.status != PaymentStatus.CANCELLED)
        .group_by(PartyPayment.aspirant_id, orphan_label)
    )
    rows = sorted(
        (
            SpendRow(aspirant=a, label=label, paid_kes=p, owed_kes=o, payments=n)
            for a, label, p, o, n in result
        ),
        key=lambda r: (r.label == "", -r.paid_kes, r.label.lower()),
    )
    return SpendReport(
        rows=rows,
        paid_kes=sum(r.paid_kes for r in rows),
        owed_kes=sum(r.owed_kes for r in rows),
    )
