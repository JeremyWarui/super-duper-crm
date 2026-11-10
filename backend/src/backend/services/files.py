"""Uploads: what is accepted, how images are cleaned and sized, and where files live.

Images (JPEG, PNG, WebP, up to 5 MB) are decoded and re-encoded at `WIDTHS`, which drops
their metadata, location included; PDFs (up to 10 MB) are kept as sent. A file's type is read
from its content, and must match the type it was sent as.
"""

import asyncio
import io
import uuid
import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models import FileArea, StoredFile, User
from backend.security import sha256_hex
from backend.services.audit import record
from backend.services.errors import Refused

MB = 1024 * 1024
IMAGE_MAX = 5 * MB
PDF_MAX = 10 * MB
# Widths an image is kept at; a narrower original is kept at its own width as well.
WIDTHS = (480, 960, 1920)
# Larger images are refused rather than decoded.
MAX_PIXELS = 40_000_000
MAX_SIDE = 20_000

PDF = "application/pdf"
IMAGE_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", PDF: ".pdf"}
SAVE_OPTIONS = {
    "JPEG": {"quality": 85, "optimize": True},
    "PNG": {"optimize": True},
    "WEBP": {"quality": 85},
}


class TooLarge(Refused):
    """The upload is over its type's size limit."""


def upload_dir() -> Path:
    return Path(get_settings().upload_dir)


def path_of(file: StoredFile, width: int | None = None) -> Path:
    """Where a PDF, or an image at one of its widths, is kept."""
    extension = EXTENSIONS[file.content_type]
    if file.content_type == PDF:
        return upload_dir() / f"{file.id}{extension}"
    return upload_dir() / f"{file.id}-{width}{extension}"


def width_for(file: StoredFile, wanted: int | None) -> int | None:
    """The narrowest kept width at least as wide as wanted, else the widest; None for a PDF."""
    if not file.widths:
        return None
    if wanted is None:
        return max(file.widths)
    return min((w for w in file.widths if w >= wanted), default=max(file.widths))


def _image(raw: bytes) -> Image.Image:
    """The decoded image, or Refused for anything that is not a JPEG, PNG or WebP."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(raw))
            if image.width * image.height > MAX_PIXELS or max(image.size) > MAX_SIDE:
                raise Refused("That image is too large to use; resize it first.")
            image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise Refused("That file is not a JPEG, PNG, WebP image or a PDF.") from error
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise Refused("That image is too large to use; resize it first.") from error
    if image.format not in IMAGE_TYPES:
        raise Refused("That file is not a JPEG, PNG, WebP image or a PDF.")
    return image


def _renditions(image: Image.Image) -> list[tuple[int, bytes]]:
    """The image upright and re-encoded at each kept width, with no metadata."""
    kind = image.format
    upright = ImageOps.exif_transpose(image)
    if kind == "JPEG" and upright.mode not in ("RGB", "L"):
        upright = upright.convert("RGB")
    widths = sorted({w for w in WIDTHS if w < upright.width} | {min(upright.width, WIDTHS[-1])})
    out = []
    for width in widths:
        height = max(1, round(upright.height * width / upright.width))
        sized = (
            upright.copy()
            if width == upright.width
            else upright.resize((width, height), Image.Resampling.LANCZOS)
        )
        sized.info = {}
        buffer = io.BytesIO()
        sized.save(buffer, format=kind, **SAVE_OPTIONS[kind])
        out.append((width, buffer.getvalue()))
    return out


def prepare(raw: bytes, declared_type: str | None) -> tuple[str, list[tuple[int | None, bytes]]]:
    """Check an upload and return its content type and the bytes to keep at each width.

    Refuses a file over its limit, of another type, or sent as a type it is not.
    """
    if raw.startswith(b"%PDF-"):
        if len(raw) > PDF_MAX:
            raise TooLarge("A PDF may be up to 10 MB.")
        if b"%%EOF" not in raw[-1024:]:
            raise Refused("That file is not a whole PDF.")
        content_type, kept = PDF, [(None, raw)]
    else:
        if len(raw) > IMAGE_MAX:
            raise TooLarge("An image may be up to 5 MB.")
        image = _image(raw)
        content_type = IMAGE_TYPES[image.format]
        kept = list(_renditions(image))
    if declared_type != content_type:
        raise Refused("That file is not the type it was sent as.")
    return content_type, kept


def _write(paths: list[tuple[Path, bytes]]) -> None:
    upload_dir().mkdir(parents=True, exist_ok=True)
    for path, data in paths:
        path.write_bytes(data)


async def store(
    session: AsyncSession,
    raw: bytes,
    *,
    name: str,
    declared_type: str | None,
    area: FileArea,
    public: bool,
    actor: User,
) -> StoredFile:
    """Check, clean and keep an upload, and record it; committed."""
    content_type, kept = await asyncio.to_thread(prepare, raw, declared_type)
    file = StoredFile(
        id=uuid.uuid4(),
        area=area,
        public=public,
        original_name=(name or "upload")[:255],
        content_type=content_type,
        size=len(raw),
        sha256=sha256_hex(raw),
        widths=[w for w, _ in kept if w is not None],
    )
    file.uploaded_by_id = actor.id
    written = [(path_of(file, w), data) for w, data in kept]
    await asyncio.to_thread(_write, written)
    session.add(file)
    record(
        session,
        actor=actor,
        action="file.upload",
        subject_type="stored_file",
        subject_id=file.id,
        detail={"area": area.value, "type": content_type, "size": len(raw)},
    )
    try:
        await session.commit()
    except Exception:
        for path, _ in written:
            path.unlink(missing_ok=True)
        raise
    return file
