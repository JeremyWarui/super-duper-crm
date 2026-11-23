"""The website's posts: published ones for the public, all of them for the editors."""

import uuid
from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_or_refuse
from backend.models import County, Post, PostKind, PostLabel, User
from backend.schemas.content import PostCreate, PostUpdate
from backend.services.audit import record
from backend.services.errors import NotFound, Refused

NEWS_PAGE = 20


# ---- public ----


def public_posts() -> Select:
    """Published posts, with their county loaded."""
    return select(Post).options(selectinload(Post.county)).where(Post.published.is_(True))


async def published_news(
    session: AsyncSession, offset: int, label: PostLabel | None = None
) -> list[Post]:
    query = public_posts().where(Post.kind == PostKind.NEWS)
    if label is not None:
        query = query.where(Post.label == label)
    return list(
        await session.scalars(
            query.order_by(Post.published_on.desc(), Post.created_at.desc())
            .offset(offset)
            .limit(NEWS_PAGE)
        )
    )


async def upcoming_events(
    session: AsyncSession, on: date, county_id: uuid.UUID | None = None
) -> list[Post]:
    query = public_posts().where(Post.kind == PostKind.EVENT, Post.event_date >= on)
    if county_id is not None:
        query = query.where(Post.county_id == county_id)
    return list(await session.scalars(query.order_by(Post.event_date, Post.title)))


async def published_post(session: AsyncSession, post_id: uuid.UUID) -> Post:
    post = await session.scalar(public_posts().where(Post.id == post_id))
    if post is None:
        raise NotFound("No such post.")
    return post


# ---- editing ----


def _audit(session: AsyncSession, actor: User, action: str, row, **detail: object) -> None:
    record(
        session,
        actor=actor,
        action=action,
        subject_type="post",
        subject_id=row.id,
        detail=detail,
    )


async def posts(session: AsyncSession, kind: PostKind | None) -> list[Post]:
    query = select(Post).order_by(Post.created_at.desc())
    if kind is not None:
        query = query.where(Post.kind == kind)
    return list(await session.scalars(query))


async def create_post(session: AsyncSession, payload: PostCreate, *, actor: User, on: date) -> Post:
    await _check_county(session, payload.county_id)
    post = Post(**payload.model_dump())
    if post.published:
        post.published_on = on
    session.add(post)
    await session.flush()
    _audit(session, actor, "site.post.create", post, kind=post.kind.value, published=post.published)
    await session.commit()
    return post


async def _check_county(session: AsyncSession, county_id: uuid.UUID | None) -> None:
    if county_id is not None and await session.get(County, county_id) is None:
        raise Refused("No such county.")


async def update_post(
    session: AsyncSession, post_id: uuid.UUID, payload: PostUpdate, *, actor: User, on: date
) -> Post:
    post = await get_or_refuse(session, Post, post_id, "post")
    changes = {
        name: value
        for name, value in payload.model_dump(exclude_unset=True).items()
        if value is not None or name == "county_id"
    }
    await _check_county(session, changes.get("county_id"))
    if post.kind is PostKind.NEWS and (changes.get("event_date") or changes.get("venue")):
        raise Refused("A news post has no date or venue.")
    for name, value in changes.items():
        setattr(post, name, value)
    if post.published and post.published_on is None:
        post.published_on = on
    _audit(
        session,
        actor,
        "site.post.update",
        post,
        kind=post.kind.value,
        fields=sorted(changes),
        published=post.published,
    )
    await session.commit()
    await session.refresh(post)
    return post


async def delete_post(session: AsyncSession, post_id: uuid.UUID, *, actor: User) -> None:
    post = await get_or_refuse(session, Post, post_id, "post")
    _audit(session, actor, "site.post.delete", post, kind=post.kind.value)
    await session.delete(post)
    await session.commit()
