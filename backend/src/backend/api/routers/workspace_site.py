"""The website of an aspirant installation, edited from its workspace under `site.write`.

Every route calls the services the console uses, so there is one set of content rules. Mounted
only in an aspirant installation.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel

from backend.api.deps import SessionDep, Today, require
from backend.api.install import AspirantOnlyRoute
from backend.api.routers.files import read as file_read
from backend.models import (
    AgendaIssue,
    FileArea,
    HeroSlide,
    PartyDocument,
    PartyVideo,
    PostKind,
    User,
)
from backend.schemas.candidates import ProfileRead, ProfileWrite
from backend.schemas.content import (
    DocumentAdminRead,
    DocumentCreate,
    DocumentUpdate,
    IssueAdminRead,
    IssueCreate,
    IssueUpdate,
    PostAdminRead,
    PostCreate,
    PostUpdate,
    SlideAdminRead,
    SlideCreate,
    SlideUpdate,
    VideoAdminRead,
    VideoCreate,
    VideoUpdate,
)
from backend.schemas.files import FileRead
from backend.schemas.site import SiteSettingsRead, SiteSettingsUpdate
from backend.services import campaign_page, content, files, home, site
from backend.services.errors import Refused

router = APIRouter(prefix="/workspace/site", tags=["workspace site"], route_class=AspirantOnlyRoute)
Editor = Annotated[User, Depends(require("site.write"))]


@router.post("/images/", response_model=FileRead, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile, session: SessionDep, user: Editor, area: Annotated[FileArea, Form()]
) -> FileRead:
    """Upload a public JPEG, PNG or WebP image (up to 5 MB) for the site, or a PDF (up to
    10 MB) for the documents area."""
    raw = await file.read(files.PDF_MAX + 1)
    try:
        if raw.startswith(b"%PDF-") and area is not FileArea.DOCUMENTS:
            raise Refused("Choose a JPEG, PNG or WebP image.")
        stored = await files.store(
            session,
            raw,
            name=file.filename or "",
            declared_type=file.content_type,
            area=area,
            public=True,
            actor=user,
        )
    except files.TooLarge as error:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(error)) from None
    except Refused as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from None
    return file_read(stored)


@router.get("/settings/", response_model=SiteSettingsRead)
async def read_settings(session: SessionDep, _: Editor):
    return await site.read_settings(session)


@router.put("/settings/", response_model=SiteSettingsRead)
async def update_settings(payload: SiteSettingsUpdate, session: SessionDep, user: Editor):
    """Replace the site settings; colours must pass the contrast check."""
    return await site.update_settings(session, payload, actor=user)


@router.get("/candidate/", response_model=ProfileRead)
async def read_candidate_page(session: SessionDep, _: Editor):
    """The candidate page the homepage shows, as written so far."""
    return await campaign_page.read(session)


@router.put("/candidate/", response_model=ProfileRead)
async def write_candidate_page(payload: ProfileWrite, session: SessionDep, user: Editor):
    """Replace the candidate page; it shows on the homepage once published."""
    return await campaign_page.write(session, payload, actor=user)


@router.get("/posts/", response_model=list[PostAdminRead])
async def posts(session: SessionDep, _: Editor, kind: PostKind | None = None):
    """Every post, drafts included, newest first."""
    return await content.posts(session, kind)


@router.post("/posts/", response_model=PostAdminRead, status_code=status.HTTP_201_CREATED)
async def create_post(payload: PostCreate, session: SessionDep, user: Editor, today: Today):
    return await content.create_post(session, payload, actor=user, on=today)


@router.patch("/posts/{post_id}/", response_model=PostAdminRead)
async def update_post(
    post_id: uuid.UUID, payload: PostUpdate, session: SessionDep, user: Editor, today: Today
):
    return await content.update_post(session, post_id, payload, actor=user, on=today)


@router.delete("/posts/{post_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: uuid.UUID, session: SessionDep, user: Editor) -> Response:
    await content.delete_post(session, post_id, actor=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _items(
    path: str,
    model: type,
    create: type[BaseModel],
    update: type[BaseModel],
    read: type[BaseModel],
) -> None:
    """List, add, change and remove one kind of home page item at `path`."""

    async def every(session: SessionDep, _: Editor):
        return await home.every(session, model)

    async def add(payload: create, session: SessionDep, user: Editor):  # type: ignore[valid-type]
        return await home.create(session, model, payload, actor=user)

    async def change(
        item_id: uuid.UUID,
        payload: update,  # type: ignore[valid-type]
        session: SessionDep,
        user: Editor,
    ):
        return await home.update(session, model, item_id, payload, actor=user)

    async def remove(item_id: uuid.UUID, session: SessionDep, user: Editor) -> Response:
        await home.delete(session, model, item_id, actor=user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    name = path.strip("/")
    router.add_api_route(path, every, methods=["GET"], response_model=list[read], name=name)
    router.add_api_route(
        path,
        add,
        methods=["POST"],
        response_model=read,
        status_code=status.HTTP_201_CREATED,
        name=f"create_{name}",
    )
    router.add_api_route(
        f"{path}{{item_id}}/", change, methods=["PATCH"], response_model=read, name=f"update_{name}"
    )
    router.add_api_route(
        f"{path}{{item_id}}/",
        remove,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
        name=f"delete_{name}",
    )


_items("/slides/", HeroSlide, SlideCreate, SlideUpdate, SlideAdminRead)
_items("/issues/", AgendaIssue, IssueCreate, IssueUpdate, IssueAdminRead)
_items("/documents/", PartyDocument, DocumentCreate, DocumentUpdate, DocumentAdminRead)
_items("/videos/", PartyVideo, VideoCreate, VideoUpdate, VideoAdminRead)
