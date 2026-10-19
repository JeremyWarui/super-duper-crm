"""Read schemas build from a model object and expose only their listed fields."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    User,
    UserRole,
)
from backend.schemas.auth import LoginUser


async def test_the_login_the_browser_keeps_never_carries_the_password_hash(
    session: AsyncSession,
) -> None:
    user = User(
        username="asha",
        first_name="Asha",
        last_name="Mwangi",
        role=UserRole.CANDIDATE,
        password_hash="argon2$do-not-serialize-me",
        is_superuser=True,
    )
    session.add(user)
    await session.commit()

    schema = LoginUser.model_validate(user)
    dumped = schema.model_dump()

    assert "password_hash" not in dumped
    assert "do-not-serialize-me" not in schema.model_dump_json()
    assert dumped["full_name"] == "Asha Mwangi"
    assert dumped["role"] is UserRole.CANDIDATE
