"""Uploaded files as the API returns them."""

import uuid

from backend.models.enums import FileArea
from backend.schemas.common import ORMModel


class FileRead(ORMModel):
    """`url` serves the file; add `?w=` for an image at a narrower width."""

    id: uuid.UUID
    area: FileArea
    public: bool
    original_name: str
    content_type: str
    size: int
    widths: list[int]
    url: str = ""
