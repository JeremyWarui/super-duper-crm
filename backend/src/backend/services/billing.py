"""Campaign subscriptions: what one allows on a given day, and the finance officer's ledger.

`paid_until` always equals the `paid_until_after` of the latest live entry, or None with none.
Every entry moves it strictly later, so the latest live entry is the one ending on it.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Aspirant,
    Campaign,
    CampaignMember,
    CampaignSubscription,
    CrmPlan,
    PartySettings,
    SubscriptionEntry,
    User,
    UserRole,
)
from backend.models.enums import AccessState, EntryKind, SubscriptionHold
from backend.schemas.billing import (
    EntryRead,
    ExpiringRow,
    ExtensionCreate,
    FinanceSettingsUpdate,
    OwnSubscription,
    PaymentCreate,
    PlanCreate,
    PlanName,
    PlanTerms,
    PlanUpdate,
    Revenue,
    RevenueMonth,
    RevenuePlan,
    SubscriptionDetail,
    SubscriptionPage,
    SubscriptionRow,
)
from backend.services.audit import record
from backend.services.errors import Forbidden, NotFound, Refused, refuse_own_record

# Kenya keeps UTC+3 all year.
NAIROBI = timezone(timedelta(hours=3))
GRACE_DAYS = 7
READ_ONLY_DAYS = 7
# How far back a payment's received date may be.
OLDEST_PAYMENT_DAYS = 365

FULL_ACCESS = frozenset({AccessState.ACTIVE, AccessState.GRACE_PERIOD})
NO_ACCESS = frozenset({AccessState.PENDING_PAYMENT, AccessState.LOCKED, AccessState.CANCELLED})


def today() -> date:
    """Today's date in Nairobi."""
    return datetime.now(NAIROBI).date()


@dataclass(frozen=True)
class Access:
    state: AccessState
    paid_until: date | None
    read_only_from: date | None
    locks_on: date | None


def access(
    paid_until: date | None,
    hold: SubscriptionHold,
    on: date,
    grace_days: int = GRACE_DAYS,
    read_only_days: int = READ_ONLY_DAYS,
) -> Access:
    """The access state on day `on`, from the last paid day (inclusive) and the hold."""
    if paid_until is None:
        read_only_from = locks_on = None
    else:
        read_only_from = paid_until + timedelta(days=grace_days + 1)
        locks_on = read_only_from + timedelta(days=read_only_days)

    if hold is SubscriptionHold.CANCELLED:
        state = AccessState.CANCELLED
    elif hold is SubscriptionHold.SUSPENDED:
        state = AccessState.LOCKED
    elif paid_until is None:
        state = AccessState.PENDING_PAYMENT
    elif on <= paid_until:
        state = AccessState.ACTIVE
    elif on < read_only_from:
        state = AccessState.GRACE_PERIOD
    elif on < locks_on:
        state = AccessState.READ_ONLY
    else:
        state = AccessState.LOCKED
    return Access(state, paid_until, read_only_from, locks_on)


def extended(paid_until: date | None, starting: date, days: int) -> date:
    """The new last paid day: `days` more, from the day after the paid period or `starting`,
    whichever is later."""
    start = starting if paid_until is None else max(paid_until + timedelta(days=1), starting)
    return start + timedelta(days=days - 1)


async def lapse_days(session: AsyncSession) -> tuple[int, int]:
    """The party's grace and read-only days; the column defaults when no settings row exists."""
    row = (
        await session.execute(
            select(PartySettings.grace_days, PartySettings.read_only_days).where(
                PartySettings.id == 1
            )
        )
    ).first()
    return (row[0], row[1]) if row else (GRACE_DAYS, READ_ONLY_DAYS)


# ---- plans ----


async def plans(session: AsyncSession) -> list[CrmPlan]:
    return list(
        await session.scalars(select(CrmPlan).order_by(CrmPlan.active.desc(), CrmPlan.name))
    )


async def create_plan(session: AsyncSession, payload: PlanCreate, *, actor: User) -> CrmPlan:
    plan = CrmPlan(**payload.model_dump())
    session.add(plan)
    await session.flush()
    record(
        session,
        actor=actor,
        action="finance.plan.create",
        subject_type="crm_plan",
        subject_id=plan.id,
        detail={
            "price_kes": plan.price_kes,
            "duration_days": plan.duration_days,
            "active": plan.active,
        },
    )
    await session.commit()
    return plan


async def update_plan(
    session: AsyncSession, plan_id: uuid.UUID, payload: PlanUpdate, *, actor: User
) -> CrmPlan:
    plan = await session.get(CrmPlan, plan_id)
    if plan is None:
        raise NotFound("No such plan.")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for name, value in changes.items():
        setattr(plan, name, value)
    record(
        session,
        actor=actor,
        action="finance.plan.update",
        subject_type="crm_plan",
        subject_id=plan.id,
        detail={
            "fields": sorted(changes),
            "price_kes": plan.price_kes,
            "duration_days": plan.duration_days,
            "active": plan.active,
        },
    )
    await session.commit()
    await session.refresh(plan)
    return plan


# ---- reading subscriptions ----

_LOADS = (
    selectinload(CampaignSubscription.plan),
    selectinload(CampaignSubscription.campaign).options(
        selectinload(Campaign.candidate),
        selectinload(Campaign.county),
        selectinload(Campaign.constituency),
        selectinload(Campaign.ward),
    ),
)


def _row(sub: CampaignSubscription, on: date, lapse: tuple[int, int]) -> SubscriptionRow:
    campaign = sub.campaign
    candidate = campaign.candidate if campaign else None
    area = campaign.area if campaign else None
    return SubscriptionRow(
        id=sub.id,
        campaign_id=sub.campaign_id,
        title=campaign.title if campaign else (sub.campaign_title or ""),
        seat=campaign.seat if campaign else None,
        area_name=area.name if area else "",
        candidate_name=(candidate.full_name or candidate.username) if candidate else "",
        plan=PlanName(id=sub.plan.id, name=sub.plan.name) if sub.plan else None,
        paid_until=sub.paid_until,
        state=access(sub.paid_until, sub.hold, on, *lapse).state,
        hold=sub.hold,
    )


async def subscriptions(
    session: AsyncSession,
    on: date,
    *,
    state: AccessState | None,
    q: str,
    limit: int,
    offset: int,
) -> SubscriptionPage:
    """Every subscription with its state today, filtered by state and title, by title."""
    lapse = await lapse_days(session)
    rows = [
        _row(sub, on, lapse)
        for sub in await session.scalars(
            select(CampaignSubscription).options(*_LOADS).execution_options(populate_existing=True)
        )
    ]
    needle = q.strip().casefold()
    kept = [
        row
        for row in rows
        if (state is None or row.state is state) and needle in row.title.casefold()
    ]
    kept.sort(key=lambda row: (row.title.casefold(), str(row.id)))
    return SubscriptionPage(total=len(kept), items=kept[offset : offset + limit])


async def expiring(session: AsyncSession, on: date, days: int) -> list[ExpiringRow]:
    """Campaigns in grace or read-only, and active ones whose paid period ends within `days`,
    soonest first."""
    lapse = await lapse_days(session)
    due = on + timedelta(days=days)
    rows = []
    for sub in await session.scalars(
        select(CampaignSubscription).options(*_LOADS).execution_options(populate_existing=True)
    ):
        if sub.campaign_id is None:
            continue  # a deleted campaign has nobody to renew it
        dates = access(sub.paid_until, sub.hold, on, *lapse)
        soon = dates.state is AccessState.ACTIVE and sub.paid_until <= due
        if soon or dates.state in (AccessState.GRACE_PERIOD, AccessState.READ_ONLY):
            rows.append(
                ExpiringRow(
                    **_row(sub, on, lapse).model_dump(),
                    read_only_from=dates.read_only_from,
                    locks_on=dates.locks_on,
                )
            )
    rows.sort(key=lambda row: (row.paid_until, row.title.casefold(), str(row.id)))
    return rows


async def revenue(session: AsyncSession, start: date, end: date) -> Revenue:
    """Totals of the live payments received from `start` to `end`, by month and by plan."""
    payments = (
        await session.execute(
            select(
                SubscriptionEntry.received_on,
                SubscriptionEntry.amount_kes,
                CrmPlan.id,
                CrmPlan.name,
            )
            .join(CrmPlan, CrmPlan.id == SubscriptionEntry.plan_id)
            .where(
                SubscriptionEntry.kind == EntryKind.PAYMENT,
                SubscriptionEntry.voided_at.is_(None),
                SubscriptionEntry.received_on >= start,
                SubscriptionEntry.received_on <= end,
            )
        )
    ).all()
    months: dict[str, list[int]] = {}
    by_plan: dict[uuid.UUID, tuple[str, list[int]]] = {}
    for received_on, amount, plan_id, plan_name in payments:
        month = months.setdefault(received_on.strftime("%Y-%m"), [0, 0])
        plan = by_plan.setdefault(plan_id, (plan_name, [0, 0]))[1]
        for line in (month, plan):
            line[0] += amount
            line[1] += 1
    return Revenue(
        start=start,
        end=end,
        total_kes=sum(amount for _, amount, _, _ in payments),
        count=len(payments),
        by_month=[
            RevenueMonth(month=month, total_kes=total, count=count)
            for month, (total, count) in sorted(months.items())
        ],
        by_plan=[
            RevenuePlan(plan=PlanName(id=plan_id, name=name), total_kes=total, count=count)
            for plan_id, (name, (total, count)) in sorted(
                by_plan.items(), key=lambda item: (-item[1][1][0], item[1][0])
            )
        ],
    )


async def own(session: AsyncSession, user: User, on: date) -> OwnSubscription:
    """The caller's campaign's subscription; 403 for a login that is not on a campaign.

    A campaign without a subscription row reads as locked.
    """
    campaign_id = await session.scalar(
        select(CampaignMember.campaign_id).where(CampaignMember.user_id == user.id)
    )
    if user.role is None or user.is_superuser or campaign_id is None:
        raise Forbidden("This login is not on a campaign.")
    settings = await session.get(PartySettings, 1)
    instructions = settings.payment_instructions if settings else ""
    sub = await session.scalar(
        select(CampaignSubscription)
        .where(CampaignSubscription.campaign_id == campaign_id)
        .options(selectinload(CampaignSubscription.plan))
    )
    if sub is None:
        return OwnSubscription(
            state=AccessState.LOCKED,
            paid_until=None,
            read_only_from=None,
            locks_on=None,
            payment_instructions=instructions,
        )
    lapse = await lapse_days(session)
    dates = access(sub.paid_until, sub.hold, on, *lapse)
    terms = {}
    if user.role in (UserRole.CANDIDATE, UserRole.MANAGER):
        terms = {
            "plan": PlanTerms.model_validate(sub.plan, from_attributes=True) if sub.plan else None,
            "last_paid_on": await session.scalar(
                select(func.max(SubscriptionEntry.received_on)).where(
                    SubscriptionEntry.subscription_id == sub.id,
                    SubscriptionEntry.kind == EntryKind.PAYMENT,
                    SubscriptionEntry.voided_at.is_(None),
                )
            ),
            "hold_reason": sub.hold_reason,
        }
    return OwnSubscription(
        state=dates.state,
        held=sub.hold is SubscriptionHold.SUSPENDED,
        dated_state=access(sub.paid_until, SubscriptionHold.NONE, on, *lapse).state,
        paid_until=dates.paid_until,
        read_only_from=dates.read_only_from,
        locks_on=dates.locks_on,
        payment_instructions=instructions,
        **terms,
    )


async def subscription(
    session: AsyncSession, subscription_id: uuid.UUID, on: date
) -> SubscriptionDetail:
    """One subscription with its dates and its ledger, newest first."""
    sub = await session.scalar(
        select(CampaignSubscription)
        .where(CampaignSubscription.id == subscription_id)
        .options(*_LOADS)
        .execution_options(populate_existing=True)
    )
    if sub is None:
        raise NotFound("No such subscription.")
    lapse = await lapse_days(session)
    dates = access(sub.paid_until, sub.hold, on, *lapse)
    entries = list(
        await session.scalars(
            select(SubscriptionEntry)
            .where(SubscriptionEntry.subscription_id == sub.id)
            .options(
                selectinload(SubscriptionEntry.plan), selectinload(SubscriptionEntry.recorded_by)
            )
            .order_by(
                SubscriptionEntry.paid_until_after.desc(), SubscriptionEntry.created_at.desc()
            )
            .execution_options(populate_existing=True)
        )
    )
    return SubscriptionDetail(
        **_row(sub, on, lapse).model_dump(),
        hold_reason=sub.hold_reason,
        read_only_from=dates.read_only_from,
        locks_on=dates.locks_on,
        entries=[
            EntryRead(
                id=entry.id,
                kind=entry.kind,
                plan_name=entry.plan.name if entry.plan else None,
                amount_kes=entry.amount_kes,
                method=entry.method,
                reference=entry.reference,
                received_on=entry.received_on,
                days=entry.days,
                paid_until_before=entry.paid_until_before,
                paid_until_after=entry.paid_until_after,
                note=entry.note,
                recorded_by=entry.recorded_by.username if entry.recorded_by else None,
                created_at=entry.created_at,
                voided_at=entry.voided_at,
                void_reason=entry.void_reason,
                can_void=entry.voided_at is None and entry.paid_until_after == sub.paid_until,
            )
            for entry in entries
        ],
    )


# ---- writing ----


async def _locked(
    session: AsyncSession, subscription_id: uuid.UUID, actor: User
) -> CampaignSubscription:
    """The subscription, row-locked for this transaction; 403 when it is the officer's own."""
    sub = await session.scalar(
        select(CampaignSubscription)
        .where(CampaignSubscription.id == subscription_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if sub is None:
        raise NotFound("No such subscription.")
    if sub.campaign_id is not None:
        member_id = await session.scalar(
            select(Aspirant.member_id).where(Aspirant.campaign_id == sub.campaign_id)
        )
        refuse_own_record(actor, member_id)
    return sub


def _audit(
    session: AsyncSession, sub: CampaignSubscription, actor: User, action: str, **detail: object
) -> None:
    record(
        session,
        actor=actor,
        action=action,
        subject_type="campaign_subscription",
        subject_id=sub.id,
        campaign_id=sub.campaign_id,
        detail={
            name: value.isoformat() if isinstance(value, date) else value
            for name, value in detail.items()
        },
    )


async def set_plan(
    session: AsyncSession, subscription_id: uuid.UUID, plan_id: uuid.UUID, *, actor: User
) -> None:
    sub = await _locked(session, subscription_id, actor)
    plan = await session.get(CrmPlan, plan_id)
    if plan is None:
        raise NotFound("No such plan.")
    if not plan.active:
        raise Refused("That plan is no longer offered.")
    before = sub.plan_id
    sub.plan_id = plan.id
    _audit(
        session,
        sub,
        actor,
        "finance.subscription.plan",
        plan_id=str(plan.id),
        previous_plan_id=str(before) if before else None,
    )
    await session.commit()


async def _add_entry(
    session: AsyncSession, sub: CampaignSubscription, actor: User, **fields: object
) -> SubscriptionEntry:
    after = extended(sub.paid_until, fields["received_on"], fields["days"])
    entry = SubscriptionEntry(
        subscription_id=sub.id,
        paid_until_before=sub.paid_until,
        paid_until_after=after,
        recorded_by_id=actor.id,
        **fields,
    )
    session.add(entry)
    sub.paid_until = after
    await session.flush()
    return entry


async def record_payment(
    session: AsyncSession,
    subscription_id: uuid.UUID,
    payload: PaymentCreate,
    *,
    actor: User,
    on: date,
) -> None:
    """Add the plan's days from the later of the day after the paid period and the day received."""
    if payload.received_on > on:
        raise Refused("A payment cannot be received after today.")
    if payload.received_on < on - timedelta(days=OLDEST_PAYMENT_DAYS):
        raise Refused("That date is over a year ago; check the year.")
    sub = await _locked(session, subscription_id, actor)
    if sub.plan_id is None:
        raise Refused("Choose a plan for this campaign before recording a payment.")
    plan = await session.get(CrmPlan, sub.plan_id)
    entry = await _add_entry(
        session,
        sub,
        actor,
        kind=EntryKind.PAYMENT,
        plan_id=plan.id,
        amount_kes=payload.amount_kes,
        method=payload.method,
        reference=payload.reference,
        received_on=payload.received_on,
        days=plan.duration_days,
        note=payload.note,
    )
    _audit(
        session,
        sub,
        actor,
        "finance.subscription.payment",
        entry_id=str(entry.id),
        plan_id=str(plan.id),
        amount_kes=entry.amount_kes,
        days=entry.days,
        paid_until_before=entry.paid_until_before,
        paid_until_after=entry.paid_until_after,
    )
    await session.commit()


async def extend(
    session: AsyncSession,
    subscription_id: uuid.UUID,
    payload: ExtensionCreate,
    *,
    actor: User,
    on: date,
) -> None:
    """Add free days, counted like a payment received today."""
    sub = await _locked(session, subscription_id, actor)
    entry = await _add_entry(
        session,
        sub,
        actor,
        kind=EntryKind.EXTENSION,
        plan_id=sub.plan_id,
        received_on=on,
        days=payload.days,
        note=payload.note,
    )
    _audit(
        session,
        sub,
        actor,
        "finance.subscription.extension",
        entry_id=str(entry.id),
        days=entry.days,
        paid_until_before=entry.paid_until_before,
        paid_until_after=entry.paid_until_after,
    )
    await session.commit()


async def void(
    session: AsyncSession,
    subscription_id: uuid.UUID,
    entry_id: uuid.UUID,
    reason: str,
    *,
    actor: User,
) -> None:
    """Void the latest live entry and put the paid date back to what it was before it."""
    sub = await _locked(session, subscription_id, actor)
    entry = await session.scalar(
        select(SubscriptionEntry)
        .where(SubscriptionEntry.id == entry_id, SubscriptionEntry.subscription_id == sub.id)
        .execution_options(populate_existing=True)
    )
    if entry is None:
        raise NotFound("No such entry on this subscription.")
    if entry.voided_at is not None:
        raise Refused("That entry is already voided.")
    moved = await session.execute(
        update(CampaignSubscription)
        .where(
            CampaignSubscription.id == sub.id,
            CampaignSubscription.paid_until == entry.paid_until_after,
        )
        .values(paid_until=entry.paid_until_before, updated_at=datetime.now(UTC))
    )
    if moved.rowcount != 1:
        raise Refused("Only the latest entry can be voided; void the newer ones first.")
    entry.voided_at = datetime.now(UTC)
    entry.voided_by_id = actor.id
    entry.void_reason = reason
    _audit(
        session,
        sub,
        actor,
        "finance.subscription.void",
        entry_id=str(entry.id),
        kind=entry.kind.value,
        amount_kes=entry.amount_kes,
        paid_until_before=entry.paid_until_after,
        paid_until_after=entry.paid_until_before,
    )
    await session.commit()


async def set_hold(
    session: AsyncSession,
    subscription_id: uuid.UUID,
    hold: SubscriptionHold,
    reason: str | None,
    *,
    actor: User,
) -> None:
    """Stop or restore access; the paid date is left as it is."""
    sub = await _locked(session, subscription_id, actor)
    before = sub.hold
    sub.hold = hold
    sub.hold_reason = reason
    _audit(session, sub, actor, "finance.subscription.hold", previous=before.value, hold=hold.value)
    await session.commit()


# ---- settings ----


async def read_settings(session: AsyncSession) -> PartySettings:
    row = await session.get(PartySettings, 1)
    if row is None:
        raise NotFound("The party settings row is missing; set the party up in the console.")
    return row


async def update_settings(
    session: AsyncSession, payload: FinanceSettingsUpdate, *, actor: User
) -> PartySettings:
    row = await read_settings(session)
    values = payload.model_dump()
    changed = sorted(name for name, value in values.items() if getattr(row, name) != value)
    for name, value in values.items():
        setattr(row, name, value)
    row.updated_at = datetime.now(UTC)
    record(
        session,
        actor=actor,
        action="finance.settings",
        subject_type="party_settings",
        detail={
            "fields": changed,
            "grace_days": row.grace_days,
            "read_only_days": row.read_only_days,
        },
    )
    await session.commit()
    return row


async def campaign_access(
    session: AsyncSession, campaign_id: uuid.UUID, today: date
) -> AccessState | None:
    """A campaign's access state today; None when it has no subscription row (as locked)."""
    row = (
        await session.execute(
            select(
                CampaignSubscription.paid_until,
                CampaignSubscription.hold,
                PartySettings.grace_days,
                PartySettings.read_only_days,
            )
            .outerjoin(PartySettings, PartySettings.id == 1)
            .where(CampaignSubscription.campaign_id == campaign_id)
        )
    ).first()
    if row is None:
        return None
    paid_until, hold, grace_days, read_only_days = row
    return access(
        paid_until,
        hold,
        today,
        GRACE_DAYS if grace_days is None else grace_days,
        READ_ONLY_DAYS if read_only_days is None else read_only_days,
    ).state
