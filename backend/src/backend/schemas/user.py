"""Read schema for User.

`password_hash`, `is_superuser` and `last_login_at` are deliberately absent.
This is the whole reason the schema layer is separate from the mapped class: a
single class that is both table and wire format has no way to keep a credential
out of a response except by remembering to exclude it at every call site.
"""

import uuid
from datetime import datetime

from backend.models.enums import UserRole
from backend.schemas.common import ORMModel


class UserRead(ORMModel):
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
