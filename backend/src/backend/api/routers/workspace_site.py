"""The website of an aspirant installation, edited from its workspace under `site.write`.

Every route calls the services the console uses, so there is one set of content rules. Mounted
only in an aspirant installation.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from backend.api.content_routes import items, posts
from backend.api.deps import SessionDep, require
from backend.api.install import AspirantOnlyRoute
from backend.api.routers.files import read as file_read
from backend.models import (
    AgendaIssue,
    FileArea,
    HeroSlide,
    PartyDocument,
    PartyVideo,
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
    SlideAdminRead,
    SlideCreate,
    SlideUpdate,
    VideoAdminRead,
    VideoCreate,
    VideoUpdate,
)
from backend.schemas.files import FileRead
from backend.schemas.site import SiteSettingsRead, SiteSettingsUpdate
from backend.services import campaign_page, files, site
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


posts(router, Editor, "/posts/")
items(router, Editor, "/slides/", HeroSlide, SlideCreate, SlideUpdate, SlideAdminRead)
items(router, Editor, "/issues/", AgendaIssue, IssueCreate, IssueUpdate, IssueAdminRead)
items(
    router, Editor, "/documents/", PartyDocument, DocumentCreate, DocumentUpdate, DocumentAdminRead
)
items(router, Editor, "/videos/", PartyVideo, VideoCreate, VideoUpdate, VideoAdminRead)
