"""What a User looks like in a response."""

import uuid
from datetime import datetime

from backend.models.enums import UserRole
from backend.schemas.common import ORMModel


class UserRead(ORMModel):
    """Excludes password_hash, is_superuser and last_login_at."""

    id: uuid.UUID
    username: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    phone: str
    role: UserRole
    is_active: bool
    created_at: datetime
