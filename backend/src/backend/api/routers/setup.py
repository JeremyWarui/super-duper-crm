"""First-run setup: open before the installation is set up, when every other route is not."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Response, status

from backend.api.deps import AdminUser, SessionDep
from backend.schemas.setup import (
    Area,
    ServiceState,
    ServiceTestResult,
    SetupRequest,
    SetupResult,
    SetupToken,
)
from backend.services import setup

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/")
async def setup_state(session: SessionDep) -> dict[str, bool]:
    return {"set_up": await setup.is_set_up(session)}


@router.post("/check/", status_code=status.HTTP_204_NO_CONTENT)
async def check_token(payload: SetupToken, session: SessionDep) -> Response:
    await setup.check(session, payload.token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/areas/", response_model=list[Area])
async def setup_areas(
    session: SessionDep,
    level: Literal["county", "constituency", "ward"],
    x_setup_token: Annotated[str, Header()],
    parent: uuid.UUID | Literal[""] = "",
) -> list[Area]:
    return await setup.areas(session, x_setup_token, level, parent or None)


@router.post("/", response_model=SetupResult, status_code=status.HTTP_201_CREATED)
async def run_setup(payload: SetupRequest, session: SessionDep) -> SetupResult:
    return await setup.run(session, payload)


@router.get("/services/", response_model=list[ServiceState])
async def services(_: AdminUser) -> list[ServiceState]:
    return setup.services()


@router.post("/services/{key}/test/", response_model=ServiceTestResult)
async def test_service(key: str, user: AdminUser, session: SessionDep) -> ServiceTestResult:
    return ServiceTestResult(message=await setup.test_service(session, key, user))
