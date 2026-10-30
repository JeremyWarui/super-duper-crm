"""An audit event as the console reads it."""

import uuid
from datetime import datetime

from backend.schemas.common import ORMModel


class AuditEventRead(ORMModel):
    id: uuid.UUID
    created_at: datetime
    actor_id: uuid.UUID | None
    actor_name: str
    action: str
    subject_type: str
    subject_id: uuid.UUID | None
    campaign_id: uuid.UUID | None
    detail: dict
