"""Each public page's title, description and preview image, written into its HTML head.

Link previews (WhatsApp, Facebook, X, Telegram) read the page's HTML without running its
script, so the head has to carry them.
"""

import html
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models import AgendaIssue, CandidateProfile, HeroSlide, SiteSettings
from backend.services import campaign_page, content, home, rich_text
from backend.services.clock import NAIROBI
from backend.services.errors import NotFound

DESCRIPTION_MAX = 200

# Page addresses and their fixed titles; None takes the site's own name.
FIXED = {
    "/": None,
    "/about": "About",
    "/agenda": "Agenda",
    "/media": "Videos and documents",
    "/volunteer": "Volunteer",
    "/news": "News",
    "/events": "Events",
    "/contribute": "Contribute",
    "/privacy": "Privacy notice",
}

FALLBACK = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title></title>
  </head>
  <body></body>
</html>
"""


@dataclass
class Head:
    title: str
    description: str
    image: str
    path: str
    kind: str = "website"


def shorten(text: str, limit: int = DESCRIPTION_MAX) -> str:
    """`text` on one line, cut at a word to at most `limit` characters with an ellipsis."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[: limit - 1].rsplit(" ", 1)[0].rstrip(",.;:")
    return f"{cut}…"


async def head_for(session: AsyncSession, path: str) -> Head:
    """The head for `path`; an unknown or unpublished page gets the site's own."""
    site = await session.scalar(select(SiteSettings))
    name = site.name if site else ""
    about = (site.slogan or site.description) if site else ""
    candidate = await _candidate(session)
    image = (candidate.photo_url if candidate else "") or await _first_slide(session)
    base = Head(title=name, description=shorten(about), image=image, path=path)
    if path in FIXED:
        label = FIXED[path]
        if path == "/about" and candidate is not None:
            base.title = f"About {candidate.name} | {name}"
            base.description = shorten(rich_text.text(candidate.bio)) or base.description
        elif label:
            base.title = f"{label} | {name}"
        return base
    section, _, ref = path.strip("/").partition("/")
    try:
        if section == "news" and ref:
            post = await content.published_post(session, ref)
            return Head(
                title=f"{post.title} | {name}",
                description=shorten(rich_text.text(post.body)) or base.description,
                image=post.image_url or image,
                path=f"/news/{post.slug}" if post.slug else path,
                kind="article",
            )
        if section == "events" and ref:
            event = await content.published_event(session, uuid.UUID(ref))
            when = _day(event.scheduled_date)
            where = ", ".join(p for p in (event.venue, event.ward.name) if p)
            lead = " · ".join(p for p in (when, where) if p)
            text = rich_text.text(event.description)
            return Head(
                title=f"{event.title} | {name}",
                description=shorten(f"{lead}. {text}" if text else lead) or base.description,
                image=event.image_url or image,
                path=path,
            )
        if section == "issues" and ref:
            issue: AgendaIssue = await home.published_issue(session, uuid.UUID(ref))
            return Head(
                title=f"{issue.title} | {name}",
                description=shorten(issue.summary) or base.description,
                image=issue.image_url or image,
                path=path,
            )
    except (NotFound, ValueError):
        pass
    return base


def _day(when: datetime | None) -> str:
    """Saturday 6 December 2026, in Nairobi."""
    if when is None:
        return ""
    local = when.astimezone(NAIROBI)
    return f"{local:%A} {local.day} {local:%B %Y}"


async def _candidate(session: AsyncSession) -> "_Candidate | None":
    try:
        found = await campaign_page.campaign(session)
    except NotFound:
        return None
    profile = await session.scalar(
        select(CandidateProfile).where(CandidateProfile.campaign_id == found.id)
    )
    if profile is None or not profile.published:
        return None
    return _Candidate(found.candidate_label or found.title, profile.photo_url, profile.bio)


@dataclass
class _Candidate:
    name: str
    photo_url: str
    bio: str


async def _first_slide(session: AsyncSession) -> str:
    slides = await home.published(session, HeroSlide)
    return next((s.image_url for s in slides if s.image_url), "")


def absolute(url: str) -> str:
    """`url` as a full address; one on this site gets the public address in front."""
    return get_settings().url(url) if url.startswith("/") else url


def tags(head: Head) -> str:
    """The head's meta tags, each value escaped."""
    e = html.escape
    card = "summary_large_image" if head.image else "summary"
    lines = [
        f"<title>{e(head.title)}</title>",
        f'<meta name="description" content="{e(head.description)}" />',
        f'<link rel="canonical" href="{e(absolute(head.path))}" />',
        f'<meta property="og:type" content="{head.kind}" />',
        f'<meta property="og:title" content="{e(head.title)}" />',
        f'<meta property="og:description" content="{e(head.description)}" />',
        f'<meta property="og:url" content="{e(absolute(head.path))}" />',
        f'<meta name="twitter:card" content="{card}" />',
    ]
    if head.image:
        lines.append(f'<meta property="og:image" content="{e(absolute(head.image))}" />')
    return "\n    ".join(lines)


TITLE = re.compile(r"<title>.*?</title>", re.S)


def page(template: str, head: Head) -> str:
    """`template` with its title swapped for the head's tags."""
    return TITLE.sub(lambda _: tags(head), template, count=1)


@cache
def template(static_dir: str) -> str:
    """The built index.html, or a bare page when the API runs without the app's files."""
    index = Path(static_dir) / "index.html" if static_dir else None
    return index.read_text(encoding="utf-8") if index and index.is_file() else FALLBACK
