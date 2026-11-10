"""List, add, change and remove routes for website content, shared by the console and the
aspirant workspace."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, status
from pydantic import BaseModel

from backend.api.deps import SessionDep, Today
from backend.models import PostKind
from backend.schemas.content import PostAdminRead, PostCreate, PostUpdate
from backend.services import content, home


def items(
    router: APIRouter,
    guard: type,
    path: str,
    model: type,
    create: type[BaseModel],
    update: type[BaseModel],
    read: type[BaseModel],
    key: str = "item_id",
) -> None:
    """Add the four routes for one kind of home page item at `path`, each behind `guard`.

    `key` names the id in the item's path, as `contracts/frontend-api.json` lists it.
    """
    ItemId = Annotated[uuid.UUID, Path(alias=key)]

    async def every(session: SessionDep, _: guard):  # type: ignore[valid-type]
        return await home.every(session, model)

    async def add(payload: create, session: SessionDep, user: guard):  # type: ignore[valid-type]
        return await home.create(session, model, payload, actor=user)

    async def change(
        item_id: ItemId,
        payload: update,  # type: ignore[valid-type]
        session: SessionDep,
        user: guard,  # type: ignore[valid-type]
    ):
        return await home.update(session, model, item_id, payload, actor=user)

    async def remove(item_id: ItemId, session: SessionDep, user: guard) -> None:  # type: ignore[valid-type]
        await home.delete(session, model, item_id, actor=user)

    name = path.strip("/").replace("/", "_")
    one = f"{path}{{{key}}}/"
    router.add_api_route(path, every, methods=["GET"], response_model=list[read], name=name)
    router.add_api_route(
        path,
        add,
        methods=["POST"],
        response_model=read,
        status_code=status.HTTP_201_CREATED,
        name=f"create_{name}",
    )
    router.add_api_route(one, change, methods=["PATCH"], response_model=read, name=f"update_{name}")
    router.add_api_route(
        one,
        remove,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
        name=f"delete_{name}",
    )


def posts(router: APIRouter, guard: type, path: str) -> None:
    """Add the four post routes at `path`, each behind `guard`."""

    async def every(
        session: SessionDep,
        _: guard,  # type: ignore[valid-type]
        kind: PostKind | None = None,
    ):
        """Every post, drafts included, newest first."""
        return await content.posts(session, kind)

    async def add(payload: PostCreate, session: SessionDep, user: guard, today: Today):  # type: ignore[valid-type]
        """Add a post; publishing it sets its published date to today."""
        return await content.create_post(session, payload, actor=user, on=today)

    async def change(
        post_id: uuid.UUID,
        payload: PostUpdate,
        session: SessionDep,
        user: guard,  # type: ignore[valid-type]
        today: Today,
    ):
        """Change a post; the first publish sets its published date, later ones keep it."""
        return await content.update_post(session, post_id, payload, actor=user, on=today)

    async def remove(post_id: uuid.UUID, session: SessionDep, user: guard) -> None:  # type: ignore[valid-type]
        await content.delete_post(session, post_id, actor=user)

    name = path.strip("/").replace("/", "_")
    one = f"{path}{{post_id}}/"
    router.add_api_route(
        path, every, methods=["GET"], response_model=list[PostAdminRead], name=name
    )
    router.add_api_route(
        path,
        add,
        methods=["POST"],
        response_model=PostAdminRead,
        status_code=status.HTTP_201_CREATED,
        name=f"create_{name}",
    )
    router.add_api_route(
        one, change, methods=["PATCH"], response_model=PostAdminRead, name=f"update_{name}"
    )
    router.add_api_route(
        one,
        remove,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
        name=f"delete_{name}",
    )
