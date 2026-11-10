"""Uploaded files as routes take and give them: storing a form's file, serving a private one."""

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import FileArea, StoredFile, User
from backend.services import files
from backend.services.errors import Refused

PRIVATE = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}


async def store_upload(
    session: AsyncSession,
    file: UploadFile,
    *,
    area: FileArea,
    public: bool,
    actor: User,
    images_only: bool = False,
) -> StoredFile:
    """Store a JPEG, PNG or WebP image (up to 5 MB) or a PDF (up to 10 MB) from a form.

    With `images_only` a PDF is refused. Too large answers 413, any other refusal 400.
    """
    raw = await file.read(files.PDF_MAX + 1)
    if images_only and raw.startswith(b"%PDF-"):
        raise Refused("Choose a JPEG, PNG or WebP image.")
    return await files.store(
        session,
        raw,
        name=file.filename or "",
        declared_type=file.content_type,
        area=area,
        public=public,
        actor=actor,
    )


def private_file(stored: StoredFile, missing: str) -> FileResponse:
    """A stored private file as a download no cache keeps; 404 with `missing` when it is gone."""
    path = files.path_of(stored, files.width_for(stored, None))
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, missing)
    return FileResponse(
        path, media_type=stored.content_type, filename=stored.original_name, headers=PRIVATE
    )
