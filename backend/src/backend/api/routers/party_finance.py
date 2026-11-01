"""The finance officer's plans, campaign subscriptions, ledger and lapse settings."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.deps import FinanceOfficer, SessionDep, Today
from backend.models import AccessState
from backend.schemas.billing import (
    ExpiringRow,
    ExtensionCreate,
    FinanceSettings,
    FinanceSettingsUpdate,
    HoldChange,
    PaymentCreate,
    PlanChoice,
    PlanCreate,
    PlanRead,
    PlanUpdate,
    Revenue,
    SubscriptionDetail,
    SubscriptionPage,
    VoidCreate,
)
from backend.schemas.common import plain_text
from backend.services import billing

router = APIRouter(prefix="/party/finance", tags=["party"])

MAX_REPORT_DAYS = 3_660


@router.get("/plans/", response_model=list[PlanRead])
async def list_plans(user: FinanceOfficer, session: SessionDep) -> list:
    """Every plan, offered ones first."""
    return await billing.plans(session)


@router.post("/plans/", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
async def create_plan(payload: PlanCreate, user: FinanceOfficer, session: SessionDep):
    return await billing.create_plan(session, payload, actor=user)


@router.patch("/plans/{plan_id}/", response_model=PlanRead)
async def update_plan(
    plan_id: uuid.UUID, payload: PlanUpdate, user: FinanceOfficer, session: SessionDep
):
    """Change a plan's fields, or stop offering it with `active: false`."""
    return await billing.update_plan(session, plan_id, payload, actor=user)


@router.get("/subscriptions/", response_model=SubscriptionPage)
async def list_subscriptions(
    user: FinanceOfficer,
    session: SessionDep,
    today: Today,
    state: AccessState | None = None,
    q: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> SubscriptionPage:
    """Every campaign's subscription and its state today, by title."""
    try:
        plain_text(q)
    except ValueError as refused:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(refused)) from None
    return await billing.subscriptions(session, today, state=state, q=q, limit=limit, offset=offset)


@router.get("/subscriptions/{subscription_id}/", response_model=SubscriptionDetail)
async def get_subscription(
    subscription_id: uuid.UUID, user: FinanceOfficer, session: SessionDep, today: Today
) -> SubscriptionDetail:
    return await billing.subscription(session, subscription_id, today)


@router.put("/subscriptions/{subscription_id}/plan/", response_model=SubscriptionDetail)
async def choose_plan(
    subscription_id: uuid.UUID,
    payload: PlanChoice,
    user: FinanceOfficer,
    session: SessionDep,
    today: Today,
) -> SubscriptionDetail:
    """The plan the next payment is for; past entries keep theirs."""
    await billing.set_plan(session, subscription_id, payload.plan, actor=user)
    return await billing.subscription(session, subscription_id, today)


@router.post(
    "/subscriptions/{subscription_id}/payments/",
    response_model=SubscriptionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def record_payment(
    subscription_id: uuid.UUID,
    payload: PaymentCreate,
    user: FinanceOfficer,
    session: SessionDep,
    today: Today,
) -> SubscriptionDetail:
    await billing.record_payment(session, subscription_id, payload, actor=user, on=today)
    return await billing.subscription(session, subscription_id, today)


@router.post(
    "/subscriptions/{subscription_id}/extensions/",
    response_model=SubscriptionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def extend(
    subscription_id: uuid.UUID,
    payload: ExtensionCreate,
    user: FinanceOfficer,
    session: SessionDep,
    today: Today,
) -> SubscriptionDetail:
    """Free days, with the reason; not counted as revenue."""
    await billing.extend(session, subscription_id, payload, actor=user, on=today)
    return await billing.subscription(session, subscription_id, today)


@router.post(
    "/subscriptions/{subscription_id}/entries/{entry_id}/void/",
    response_model=SubscriptionDetail,
)
async def void_entry(
    subscription_id: uuid.UUID,
    entry_id: uuid.UUID,
    payload: VoidCreate,
    user: FinanceOfficer,
    session: SessionDep,
    today: Today,
) -> SubscriptionDetail:
    """Void the latest live entry; its days come off the paid date."""
    await billing.void(session, subscription_id, entry_id, payload.reason, actor=user)
    return await billing.subscription(session, subscription_id, today)


@router.put("/subscriptions/{subscription_id}/hold/", response_model=SubscriptionDetail)
async def set_hold(
    subscription_id: uuid.UUID,
    payload: HoldChange,
    user: FinanceOfficer,
    session: SessionDep,
    today: Today,
) -> SubscriptionDetail:
    """Suspend or cancel access with a reason, or lift the hold with `hold: none`."""
    await billing.set_hold(session, subscription_id, payload.hold, payload.reason, actor=user)
    return await billing.subscription(session, subscription_id, today)


@router.get("/settings/", response_model=FinanceSettings)
async def get_settings(user: FinanceOfficer, session: SessionDep):
    return await billing.read_settings(session)


@router.put("/settings/", response_model=FinanceSettings)
async def put_settings(payload: FinanceSettingsUpdate, user: FinanceOfficer, session: SessionDep):
    """Grace days, read-only days and the payment instructions; every campaign's state moves."""
    return await billing.update_settings(session, payload, actor=user)


@router.get("/reports/revenue/", response_model=Revenue)
async def revenue_report(
    user: FinanceOfficer,
    session: SessionDep,
    today: Today,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
) -> Revenue:
    """Live payments received between two days, both included; this calendar year by default."""
    start = start or date(today.year, 1, 1)
    end = end or date(today.year, 12, 31)
    if start > end:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The start is after the end.")
    if (end - start).days > MAX_REPORT_DAYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ask for ten years or less.")
    return await billing.revenue(session, start, end)


@router.get("/reports/expiring/", response_model=list[ExpiringRow])
async def expiring_report(
    user: FinanceOfficer,
    session: SessionDep,
    today: Today,
    days: Annotated[int, Query(ge=1, le=90)] = 14,
) -> list[ExpiringRow]:
    """Campaigns in grace or read-only, and those whose paid period ends within `days`."""
    return await billing.expiring(session, today, days)
