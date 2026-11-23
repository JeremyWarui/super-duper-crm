"""Response builders that more than one router returns."""

from backend.models import PaymentIn, StoredFile
from backend.schemas.files import FileRead
from backend.schemas.payments_in import PaymentInRead


def payment_in_read[Model: PaymentInRead](
    row: PaymentIn, model: type[Model] = PaymentInRead
) -> Model:
    return model.model_validate(row, from_attributes=True).model_copy(
        update={"practice": row.provider == "practice"}
    )


def file_read(file: StoredFile) -> FileRead:
    return FileRead.model_validate(file).model_copy(update={"url": f"/api/files/{file.id}/"})
