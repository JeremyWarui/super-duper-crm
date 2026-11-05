"""Uploads: what is refused, what is stripped, and who may fetch a file."""

import io
from pathlib import Path

import httpx
import pytest
from PIL import ExifTags, Image

from backend.config import get_settings
from tests.conftest import World

URL = "/api/files/"


@pytest.fixture(autouse=True)
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def _jpeg(width: int = 1000, *, gps: bool = False) -> bytes:
    image = Image.new("RGB", (width, width // 2), "steelblue")
    exif = Image.Exif()
    if gps:
        exif[ExifTags.Base.Make] = "Phone"
        exif[ExifTags.IFD.GPSInfo] = {
            ExifTags.GPS.GPSLatitudeRef: "S",
            ExifTags.GPS.GPSLatitude: (1.0, 17.0, 30.0),
        }
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes())
    return buffer.getvalue()


async def _upload(
    client: httpx.AsyncClient,
    headers: dict,
    data: bytes,
    content_type: str,
    *,
    name: str = "photo.jpg",
    public: bool = True,
) -> httpx.Response:
    return await client.post(
        URL,
        headers=headers,
        files={"file": (name, data, content_type)},
        data={"area": "leaders", "public": str(public).lower()},
    )


@pytest.mark.parametrize(
    ("data", "content_type"),
    [
        (b"%PDF-1.7\n%%EOF", "image/png"),
        (b"<script>alert(1)</script>", "image/png"),
        (_jpeg(), "image/png"),
        (_jpeg(), "application/pdf"),
        (b"%PDF-<html><script>alert(1)</script></html>", "application/pdf"),
    ],
    ids=["pdf-as-png", "text-as-png", "jpeg-as-png", "jpeg-as-pdf", "html-behind-a-pdf-marker"],
)
async def test_a_disguised_file_is_refused(
    client: httpx.AsyncClient, admin_headers: dict, upload_dir: Path, data: bytes, content_type: str
) -> None:
    answer = await _upload(client, admin_headers, data, content_type)

    assert answer.status_code == 400
    assert list(upload_dir.iterdir()) == []


@pytest.mark.parametrize(
    ("data", "content_type"),
    [
        (b"%PDF-1.7\n" + b"0" * (10 * 1024 * 1024), "application/pdf"),
        (b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024), "image/jpeg"),
    ],
    ids=["pdf-over-10mb", "image-over-5mb"],
)
async def test_an_over_size_file_is_refused(
    client: httpx.AsyncClient, admin_headers: dict, data: bytes, content_type: str
) -> None:
    answer = await _upload(client, admin_headers, data, content_type)

    assert answer.status_code == 413


async def test_location_and_other_metadata_are_stripped(
    client: httpx.AsyncClient, admin_headers: dict
) -> None:
    sent = _jpeg(gps=True)
    assert Image.open(io.BytesIO(sent)).getexif().get_ifd(ExifTags.IFD.GPSInfo)

    uploaded = (await _upload(client, admin_headers, sent, "image/jpeg")).json()
    kept = await client.get(uploaded["url"])
    image = Image.open(io.BytesIO(kept.content))

    assert dict(image.getexif()) == {}
    assert "exif" not in image.info
    assert uploaded["widths"] == [480, 960, 1000]


async def test_a_private_file_is_served_only_to_a_superuser(
    client: httpx.AsyncClient, world: World, admin_headers: dict
) -> None:
    pdf = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF"
    uploaded = await _upload(
        client, admin_headers, pdf, "application/pdf", name="minutes.pdf", public=False
    )
    url = uploaded.json()["url"]

    anonymous = await client.get(url)
    manager = await client.get(url, headers=world.headers("manager"))
    superuser = await client.get(url, headers=admin_headers)

    assert (anonymous.status_code, manager.status_code) == (404, 404)
    assert superuser.status_code == 200
    assert superuser.content == pdf
    assert superuser.headers["cache-control"] == "private, no-store"


async def test_a_public_image_is_served_with_caching_headers_at_the_width_asked(
    client: httpx.AsyncClient, admin_headers: dict
) -> None:
    uploaded = (await _upload(client, admin_headers, _jpeg(2400), "image/jpeg")).json()

    full = await client.get(uploaded["url"])
    small = await client.get(f"{uploaded['url']}?w=500")

    assert full.status_code == 200
    assert full.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert full.headers["content-type"] == "image/jpeg"
    assert full.headers["etag"]
    assert Image.open(io.BytesIO(full.content)).width == 1920
    assert Image.open(io.BytesIO(small.content)).width == 960


async def test_only_a_superuser_uploads(client: httpx.AsyncClient, world: World) -> None:
    answer = await _upload(client, world.headers("manager"), _jpeg(), "image/jpeg")

    assert answer.status_code == 403
