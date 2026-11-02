"""The party's leaders and posts: published ones for the public, all of them for the superuser."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PartyLeader, PartyPost, PostKind, User
from backend.schemas.content import LeaderCreate, LeaderUpdate, PostCreate, PostUpdate
from backend.services.audit import record
from backend.services.errors import NotFound, Refused

NEWS_PAGE = 20


# ---- public ----


async def published_leaders(session: AsyncSession) -> list[PartyLeader]:
    return list(
        await session.scalars(
            select(PartyLeader)
            .where(PartyLeader.published.is_(True))
            .order_by(PartyLeader.sort_order, PartyLeader.name)
        )
    )


async def published_news(session: AsyncSession, offset: int) -> list[PartyPost]:
    return list(
        await session.scalars(
            select(PartyPost)
            .where(PartyPost.kind == PostKind.NEWS, PartyPost.published.is_(True))
            .order_by(PartyPost.published_on.desc(), PartyPost.created_at.desc())
            .offset(offset)
            .limit(NEWS_PAGE)
        )
    )


async def upcoming_events(session: AsyncSession, on: date) -> list[PartyPost]:
    return list(
        await session.scalars(
            select(PartyPost)
            .where(
                PartyPost.kind == PostKind.EVENT,
                PartyPost.published.is_(True),
                PartyPost.event_date >= on,
            )
            .order_by(PartyPost.event_date, PartyPost.title)
        )
    )


async def published_post(session: AsyncSession, post_id: uuid.UUID) -> PartyPost:
    post = await session.scalar(
        select(PartyPost).where(PartyPost.id == post_id, PartyPost.published.is_(True))
    )
    if post is None:
        raise NotFound("No such post.")
    return post


# ---- editing ----


def _audit(session: AsyncSession, actor: User, action: str, row, **detail: object) -> None:
    record(
        session,
        actor=actor,
        action=action,
        subject_type="party_leader" if isinstance(row, PartyLeader) else "party_post",
        subject_id=row.id,
        detail=detail,
    )


async def leaders(session: AsyncSession) -> list[PartyLeader]:
    return list(
        await session.scalars(
            select(PartyLeader).order_by(PartyLeader.sort_order, PartyLeader.name)
        )
    )


async def create_leader(
    session: AsyncSession, payload: LeaderCreate, *, actor: User
) -> PartyLeader:
    leader = PartyLeader(**payload.model_dump())
    session.add(leader)
    await session.flush()
    _audit(session, actor, "party.leader.create", leader, published=leader.published)
    await session.commit()
    return leader


async def _leader(session: AsyncSession, leader_id: uuid.UUID) -> PartyLeader:
    leader = await session.get(PartyLeader, leader_id)
    if leader is None:
        raise NotFound("No such leader.")
    return leader


async def update_leader(
    session: AsyncSession, leader_id: uuid.UUID, payload: LeaderUpdate, *, actor: User
) -> PartyLeader:
    leader = await _leader(session, leader_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for name, value in changes.items():
        setattr(leader, name, value)
    _audit(
        session,
        actor,
        "party.leader.update",
        leader,
        fields=sorted(changes),
        published=leader.published,
    )
    await session.commit()
    await session.refresh(leader)
    return leader


async def delete_leader(session: AsyncSession, leader_id: uuid.UUID, *, actor: User) -> None:
    leader = await _leader(session, leader_id)
    _audit(session, actor, "party.leader.delete", leader)
    await session.delete(leader)
    await session.commit()


async def posts(session: AsyncSession, kind: PostKind | None) -> list[PartyPost]:
    query = select(PartyPost).order_by(PartyPost.created_at.desc())
    if kind is not None:
        query = query.where(PartyPost.kind == kind)
    return list(await session.scalars(query))


async def create_post(
    session: AsyncSession, payload: PostCreate, *, actor: User, on: date
) -> PartyPost:
    post = PartyPost(**payload.model_dump())
    if post.published:
        post.published_on = on
    session.add(post)
    await session.flush()
    _audit(
        session, actor, "party.post.create", post, kind=post.kind.value, published=post.published
    )
    await session.commit()
    return post


async def _post(session: AsyncSession, post_id: uuid.UUID) -> PartyPost:
    post = await session.get(PartyPost, post_id)
    if post is None:
        raise NotFound("No such post.")
    return post


async def update_post(
    session: AsyncSession, post_id: uuid.UUID, payload: PostUpdate, *, actor: User, on: date
) -> PartyPost:
    post = await _post(session, post_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if post.kind is PostKind.NEWS and (changes.get("event_date") or changes.get("venue")):
        raise Refused("A news post has no date or venue.")
    for name, value in changes.items():
        setattr(post, name, value)
    if post.published and post.published_on is None:
        post.published_on = on
    _audit(
        session,
        actor,
        "party.post.update",
        post,
        kind=post.kind.value,
        fields=sorted(changes),
        published=post.published,
    )
    await session.commit()
    await session.refresh(post)
    return post


async def delete_post(session: AsyncSession, post_id: uuid.UUID, *, actor: User) -> None:
    post = await _post(session, post_id)
    _audit(session, actor, "party.post.delete", post, kind=post.kind.value)
    await session.delete(post)
    await session.commit()
