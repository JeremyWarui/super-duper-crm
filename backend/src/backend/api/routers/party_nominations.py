"""Applications to vie: the timetable (officer drafts, Super Admin publishes), the public notice,
a member's own application from their account, and the officer's fee and document views."""

import uuid

from fastapi import APIRouter, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse

from backend.api.deps import AdminUser, NominationsOfficer, SessionDep, SignedInUser, Today
from backend.api.install import PartyOnlyRoute
from backend.api.routers.account import AccountMember
from backend.api.routers.party_aspirants import _read as read_aspirant
from backend.models import (
    Aspirant,
    Constituency,
    County,
    FileArea,
    NominationWindow,
    PartyMember,
    Ward,
)
from backend.schemas.aspirants import AspirantRead, DocumentRead
from backend.schemas.nominations import (
    ApplyFor,
    Declaration,
    FeePaid,
    MyApplication,
    MyNomination,
    PublicWindow,
    SeatChoice,
    SeatFee,
    WindowRead,
    WindowWrite,
)
from backend.services import aspirants, files, nominations
from backend.services.errors import Refused

router = APIRouter(prefix="/party/nominations", tags=["party"], route_class=PartyOnlyRoute)

DOCUMENT_LABEL_MAX = 100


def _window(row: NominationWindow, me: uuid.UUID | None = None) -> WindowRead:
    return WindowRead(
        id=row.id,
        title=row.title,
        opens_on=row.opens_on,
        closes_on=row.closes_on,
        requirements=row.requirements,
        status=row.status,
        published_at=row.published_at,
        seats=[SeatFee(seat=s.seat, fee_kes=s.fee_kes) for s in row.seats],
        mine=me is not None and row.drafted_by_id == me,
    )


def _public(row: NominationWindow, today) -> PublicWindow:
    return PublicWindow(
        title=row.title,
        opens_on=row.opens_on,
        closes_on=row.closes_on,
        requirements=row.requirements,
        open=nominations.is_open(row, today),
        seats=[SeatFee(seat=s.seat, fee_kes=s.fee_kes) for s in row.seats],
    )


def _fields(payload: WindowWrite) -> dict:
    return {
        "title": payload.title,
        "opens_on": payload.opens_on,
        "closes_on": payload.closes_on,
        "requirements": payload.requirements.strip(),
        "seats": [(s.seat, s.fee_kes) for s in payload.seats],
    }


# The officer's timetable


@router.get("/windows/", response_model=list[WindowRead])
async def list_windows(session: SessionDep, user: NominationsOfficer) -> list[WindowRead]:
    return [_window(w, user.id) for w in await nominations.windows(session)]


@router.post("/windows/", response_model=WindowRead, status_code=status.HTTP_201_CREATED)
async def draft_window(
    payload: WindowWrite, session: SessionDep, user: NominationsOfficer
) -> WindowRead:
    """Draft a timetable; the Party Super Admin publishes it."""
    return _window(await nominations.draft(session, **_fields(payload), actor=user), user.id)


@router.put("/windows/{window_id}/", response_model=WindowRead)
async def revise_window(
    window_id: uuid.UUID, payload: WindowWrite, session: SessionDep, user: NominationsOfficer
) -> WindowRead:
    row = await nominations.window(session, window_id)
    return _window(await nominations.revise(session, row, **_fields(payload), actor=user), user.id)


@router.post("/windows/{window_id}/publish/", response_model=WindowRead)
async def publish_window(
    window_id: uuid.UUID, session: SessionDep, user: AdminUser, today: Today
) -> WindowRead:
    """The Party Super Admin publishes a timetable someone else drafted."""
    row = await nominations.window(session, window_id)
    return _window(await nominations.publish(session, row, actor=user, today=today), user.id)


@router.post("/applications/{aspirant_id}/fee/", response_model=AspirantRead)
async def mark_fee_paid(
    aspirant_id: uuid.UUID, payload: FeePaid, session: SessionDep, user: NominationsOfficer
) -> AspirantRead:
    """Record an application's nomination fee paid, under its M-Pesa or bank reference."""
    aspirant = await aspirants.get_aspirant(session, aspirant_id)
    await nominations.mark_fee_paid(session, aspirant, payload.reference, actor=user)
    return read_aspirant(await aspirants.get_aspirant(session, aspirant_id))


@router.get("/applications/{aspirant_id}/documents/{document_id}/")
async def application_document(
    aspirant_id: uuid.UUID, document_id: uuid.UUID, session: SessionDep, _: NominationsOfficer
) -> FileResponse:
    stored = await nominations.document(session, aspirant_id, document_id)
    path = files.path_of(stored, files.width_for(stored, None))
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The document file is missing.")
    return FileResponse(path, media_type=stored.content_type, filename=stored.original_name)


# The public notice


@router.get("/current/", response_model=PublicWindow | None)
async def current_window(session: SessionDep, today: Today) -> PublicWindow | None:
    """The published timetable open now, or the next to open; null when there is none."""
    row = await nominations.current(session, today)
    return _public(row, today) if row else None


# The member's own application


async def _area_name(session: SessionDep, member: PartyMember, seat) -> str:
    area = await nominations.member_area(session, member, seat)
    ((field, area_id),) = area.items()
    model = {"ward_id": Ward, "constituency_id": Constituency, "county_id": County}[field]
    return (await session.get(model, area_id)).name


def _place(aspirant: Aspirant) -> str:
    place = aspirant.ward or aspirant.constituency or aspirant.county
    return place.name if place else ""


async def _mine(session: SessionDep, member: PartyMember, today) -> MyNomination:
    row = await nominations.current(session, today)
    aspirant = await nominations.mine(session, member)
    choices = []
    if aspirant is None and nominations.is_open(row, today) and member.ward_id is not None:
        choices = [
            SeatChoice(
                seat=s.seat, fee_kes=s.fee_kes, area=await _area_name(session, member, s.seat)
            )
            for s in row.seats
        ]
    return MyNomination(
        window=_public(row, today) if row else None,
        choices=choices,
        application=None
        if aspirant is None
        else MyApplication(
            id=aspirant.id,
            seat=aspirant.seat,
            area=_place(aspirant),
            status=aspirant.status,
            status_reason=aspirant.status_reason,
            fee_kes=aspirant.fee_kes,
            fee_paid=aspirant.fee_paid_at is not None,
            declared_at=aspirant.declared_at,
            from_window=aspirant.window_id is not None,
            documents=[DocumentRead(id=d.id, label=d.label) for d in aspirant.documents],
        ),
    )


@router.get("/mine/", response_model=MyNomination)
async def my_nomination(member: AccountMember, session: SessionDep, today: Today) -> MyNomination:
    return await _mine(session, member, today)


@router.post("/mine/", response_model=MyNomination, status_code=status.HTTP_201_CREATED)
async def apply(
    payload: ApplyFor, member: AccountMember, user: SignedInUser, session: SessionDep, today: Today
) -> MyNomination:
    """Start an application for a seat open now, in the member's own area."""
    await nominations.apply(session, member, payload.seat, actor=user, today=today)
    return await _mine(session, member, today)


@router.post("/mine/documents/", response_model=MyNomination, status_code=status.HTTP_201_CREATED)
async def attach_document(
    file: UploadFile,
    member: AccountMember,
    user: SignedInUser,
    session: SessionDep,
    today: Today,
    label: str = Form(min_length=1, max_length=DOCUMENT_LABEL_MAX),
) -> MyNomination:
    """A document for the application, as a PDF or a photo; private to the nominations office."""
    nominations._own_draft(await nominations.mine(session, member))
    raw = await file.read(files.PDF_MAX + 1)
    try:
        stored = await files.store(
            session,
            raw,
            name=file.filename or "",
            declared_type=file.content_type,
            area=FileArea.NOMINATIONS,
            public=False,
            actor=user,
        )
    except files.TooLarge as error:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(error)) from None
    except Refused as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from None
    await nominations.attach(
        session, await nominations.mine(session, member), stored, label.strip(), actor=user
    )
    return await _mine(session, member, today)


@router.delete("/mine/documents/{document_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def detach_document(
    document_id: uuid.UUID, member: AccountMember, session: SessionDep
) -> Response:
    await nominations.detach(session, await nominations.mine(session, member), document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/mine/submit/", response_model=MyNomination)
async def submit(
    payload: Declaration,
    member: AccountMember,
    user: SignedInUser,
    session: SessionDep,
    today: Today,
) -> MyNomination:
    """Send the application for vetting with the declaration; any fee must be marked paid."""
    if not payload.declaration:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Confirm the declaration to submit.")
    await nominations.submit(
        session, await nominations.mine(session, member), actor=user, today=today
    )
    return await _mine(session, member, today)


@router.post("/mine/withdraw/", response_model=MyNomination)
async def withdraw(
    member: AccountMember, user: SignedInUser, session: SessionDep, today: Today
) -> MyNomination:
    await nominations.withdraw(session, await nominations.mine(session, member), actor=user)
    return await _mine(session, member, today)
