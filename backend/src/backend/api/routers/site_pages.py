"""The public pages' HTML with each page's own title and link preview, and the site icon."""

import html
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.api.deps import SessionDep
from backend.config import get_settings
from backend.models import SiteSettings
from backend.services import page_head

logger = logging.getLogger(__name__)
router = APIRouter(include_in_schema=False)

# The page names the build's hashed scripts, so a browser checks for a new one every time.
CACHE = "no-cache"


async def _page(request: Request, session: SessionDep) -> HTMLResponse:
    """The page with its own head; the plain app page when the database cannot answer."""
    template = page_head.template(get_settings().static_dir)
    try:
        head = await page_head.head_for(session, request.url.path.rstrip("/") or "/")
    except (SQLAlchemyError, OSError):
        logger.exception("Page head for %s", request.url.path)
        return HTMLResponse(template, headers={"Cache-Control": "no-store"})
    return HTMLResponse(page_head.page(template, head), headers={"Cache-Control": CACHE})


for path in page_head.FIXED:
    router.add_api_route(path, _page, methods=["GET"])
for section in ("news", "events", "issues"):
    router.add_api_route(f"/{section}/{{ref}}", _page, methods=["GET"])


@router.get("/favicon.svg")
async def favicon(session: SessionDep) -> Response:
    """The site's logo, or its logo tile: initials in the accent colour on the primary."""
    site = await session.scalar(select(SiteSettings))
    if site and site.logo_url:
        return RedirectResponse(page_head.absolute(site.logo_url), headers={"Cache-Control": CACHE})
    primary = site.primary_colour if site else "#0b5d3b"
    accent = site.secondary_colour if site else "#f2b705"
    letters = html.escape(_mark(site.short_name, site.name) if site else "")
    size = 26 if len(letters) > 2 else 36
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        f'<rect width="64" height="64" rx="14" fill="{primary}"/>'
        f'<text x="32" y="33" font-family="system-ui,sans-serif" font-size="{size}" '
        f'font-weight="800" fill="{accent}" text-anchor="middle" dominant-baseline="central">'
        f"{letters}</text></svg>"
    )
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": CACHE})


def _mark(short: str, name: str) -> str:
    """Up to three characters of the short name, else the first letters of two words."""
    short = short.strip()
    if short and len(short) <= 3:
        return short
    return "".join(w[0].upper() for w in (name or short).split()[:2])
