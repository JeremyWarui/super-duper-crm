"""Uploaded files: the superuser uploads them; public ones are served to anyone, private ones
only to a superuser."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from backend.api.deps import AdminUser, SessionDep, _header, get_signed_in_user
from backend.models import FileArea, StoredFile, User
from backend.schemas.files import FileRead
from backend.services import files
from backend.services.errors import Refused

router = APIRouter(prefix="/files", tags=["files"])

# Public files never change under their id, so caches may keep them.
PUBLIC_CACHE = "public, max-age=31536000, immutable"
PRIVATE_CACHE = "private, no-store"


async def _caller(
    session: SessionDep, request: Request, header: Annotated[str | None, Depends(_header)]
) -> User | None:
    """The signed-in caller, or None for an anonymous or unknown one, or a superuser whose
    session has not passed 2-step."""
    if not header:
        return None
    try:
        user = await get_signed_in_user(session, request, header)
    except HTTPException:
        return None
    return user if request.state.two_step or not user.is_superuser else None


def read(file: StoredFile) -> FileRead:
    return FileRead.model_validate(file).model_copy(update={"url": f"/api/files/{file.id}/"})


@router.post("/", response_model=FileRead, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile,
    session: SessionDep,
    user: AdminUser,
    area: Annotated[FileArea, Form()],
    public: Annotated[bool, Form()] = True,
) -> FileRead:
    """Upload a JPEG, PNG or WebP image (up to 5 MB) or a PDF (up to 10 MB)."""
    raw = await file.read(files.PDF_MAX + 1)
    try:
        stored = await files.store(
            session,
            raw,
            name=file.filename or "",
            declared_type=file.content_type,
            area=area,
            public=public,
            actor=user,
        )
    except files.TooLarge as error:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(error)) from None
    except Refused as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from None
    return read(stored)


@router.get("/{file_id}/")
async def fetch(
    file_id: uuid.UUID,
    session: SessionDep,
    caller: Annotated[User | None, Depends(_caller)],
    w: Annotated[int | None, Query(ge=1, le=10_000)] = None,
) -> FileResponse:
    """A file; an image at the narrowest kept width of at least `w`. A private file answers
    404 to anyone but a superuser."""
    file = await session.get(StoredFile, file_id)
    allowed = file is not None and (file.public or (caller is not None and caller.is_superuser))
    if not allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such file.")
    width = files.width_for(file, w)
    path = files.path_of(file, width)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such file.")
    return FileResponse(
        path,
        media_type=file.content_type,
        headers={
            "Cache-Control": PUBLIC_CACHE if file.public else PRIVATE_CACHE,
            "ETag": f'"{file.sha256}-{width or 0}"',
            "X-Content-Type-Options": "nosniff",
            # A file opened on its own runs no script on this origin.
            "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self'",
        },
    )
