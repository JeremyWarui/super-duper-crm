"""Homepage slides, agenda issues and party documents; the public sees published ones."""

import uuid

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AgendaIssue, HeroSlide, PartyDocument, User
from backend.services.audit import record
from backend.services.errors import NotFound, Refused

MAX_SLIDES = 5
Row = HeroSlide | AgendaIssue | PartyDocument
NAMES = {HeroSlide: "hero_slide", AgendaIssue: "agenda_issue", PartyDocument: "document"}


def _ordered(model: type[Row]):
    return select(model).order_by(model.sort_order, model.created_at)


async def published(session: AsyncSession, model: type[Row]) -> list[Row]:
    return list(await session.scalars(_ordered(model).where(model.published.is_(True))))


async def published_issue(session: AsyncSession, issue_id: uuid.UUID) -> AgendaIssue:
    issue = await session.scalar(
        select(AgendaIssue).where(AgendaIssue.id == issue_id, AgendaIssue.published.is_(True))
    )
    if issue is None:
        raise NotFound("No such issue.")
    return issue


async def every(session: AsyncSession, model: type[Row]) -> list[Row]:
    return list(await session.scalars(_ordered(model)))


def _audit(session: AsyncSession, actor: User, verb: str, row: Row, **detail: object) -> None:
    name = NAMES[type(row)]
    record(
        session,
        actor=actor,
        action=f"party.{name}.{verb}",
        subject_type=name,
        subject_id=row.id,
        detail=detail,
    )


async def _get(session: AsyncSession, model: type[Row], row_id: uuid.UUID) -> Row:
    row = await session.get(model, row_id)
    if row is None:
        raise NotFound("No such item.")
    return row


async def create(
    session: AsyncSession, model: type[Row], payload: BaseModel, *, actor: User
) -> Row:
    if model is HeroSlide:
        count = await session.scalar(select(func.count()).select_from(HeroSlide))
        if count >= MAX_SLIDES:
            raise Refused(f"The carousel holds at most {MAX_SLIDES} slides; delete one first.")
    row = model(**payload.model_dump())
    session.add(row)
    await session.flush()
    _audit(session, actor, "create", row, published=row.published)
    await session.commit()
    return row


async def update(
    session: AsyncSession, model: type[Row], row_id: uuid.UUID, payload: BaseModel, *, actor: User
) -> Row:
    row = await _get(session, model, row_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for name, value in changes.items():
        setattr(row, name, value)
    _audit(session, actor, "update", row, fields=sorted(changes), published=row.published)
    await session.commit()
    await session.refresh(row)
    return row


async def delete(
    session: AsyncSession, model: type[Row], row_id: uuid.UUID, *, actor: User
) -> None:
    row = await _get(session, model, row_id)
    _audit(session, actor, "delete", row)
    await session.delete(row)
    await session.commit()
