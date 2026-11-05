"""Uploaded files: logos, photos and documents kept on disk under `UPLOAD_DIR`."""

import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_type
from backend.models.enums import FileArea


class StoredFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One upload. An image is kept re-encoded at each of `widths`; a PDF as sent."""

    __tablename__ = "stored_files"

    area: Mapped[FileArea] = mapped_column(choice_type(FileArea, "file_area"))
    # A public file is served to anyone; a private one only to a superuser.
    public: Mapped[bool] = mapped_column(Boolean, default=True)
    original_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(50))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    widths: Mapped[list[int]] = mapped_column(JSON, default=list)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
