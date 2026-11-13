"""Response builders that more than one router returns."""

from backend.models import Aspirant, PaymentIn, StoredFile
from backend.models.campaign import AREA_FIELD
from backend.schemas.aspirants import AspirantArea, AspirantRead, CandidateRead, DocumentRead
from backend.schemas.files import FileRead
from backend.schemas.payments_in import PaymentInRead


def aspirant_read(row: Aspirant) -> AspirantRead:
    level = AREA_FIELD[row.seat.office_level]
    place = getattr(row, level)
    return AspirantRead(
        id=row.id,
        member=CandidateRead.model_validate(row.member),
        seat=row.seat,
        area=AspirantArea(level=level, id=place.id, name=place.name),
        status=row.status,
        status_reason=row.status_reason,
        decided_at=row.decided_at,
        campaign_id=row.campaign_id,
        created_at=row.created_at,
        window_title=row.window.title if row.window else None,
        fee_kes=row.fee_kes,
        fee_paid_at=row.fee_paid_at,
        fee_reference=row.fee_reference,
        declared_at=row.declared_at,
        documents=[DocumentRead(id=d.id, label=d.label) for d in row.documents],
    )


def payment_in_read[Model: PaymentInRead](
    row: PaymentIn, model: type[Model] = PaymentInRead
) -> Model:
    return model.model_validate(row, from_attributes=True).model_copy(
        update={"practice": row.provider == "practice"}
    )


def file_read(file: StoredFile) -> FileRead:
    return FileRead.model_validate(file).model_copy(update={"url": f"/api/files/{file.id}/"})
