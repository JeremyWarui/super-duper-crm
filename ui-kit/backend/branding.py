"""
Per-party branding for the frontend.  Mount in your FastAPI app:

    from branding import router as branding_router
    app.include_router(branding_router)

One installation serves one party (see docs/Implementation_Plan.md), so branding
comes from the singleton `PartySettings` record. Replace `get_party_settings`
with a read of that record.
Only colours, names and images vary per party; spacing, type and radii are
fixed in the frontend so every party copy stays on-design.
"""
from __future__ import annotations

import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/api", tags=["branding"])

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class BrandColors(BaseModel):
    primary: str = Field(examples=["#0B5D3B"], description="Buttons, active nav, links")
    primaryHover: str = Field(examples=["#08442B"])
    primaryTint: str = Field(examples=["#E7F0EA"], description="Light tint for pills and icon tiles")
    accent: str = Field(examples=["#F2B705"], description="Highlight; text on it is ink #13201A")

    @field_validator("*")
    @classmethod
    def must_be_hex(cls, v: str) -> str:
        if not HEX.match(v):
            raise ValueError("colour must be #RRGGBB")
        return v.upper()


class Branding(BaseModel):
    partyName: str
    shortName: str = Field(max_length=3, description="Letters in the logo tile when no logo image")
    slogan: str
    registrationNo: str
    hotline: str
    logoUrl: str | None = None
    colors: BrandColors


# --- replace with a read of PartySettings -------------------------------------
_DEMO = Branding(
    partyName="Pamoja Party",
    shortName="P",
    slogan="[Party slogan]",
    registrationNo="[000]",
    hotline="[0700 000 000]",
    colors=BrandColors(primary="#0B5D3B", primaryHover="#08442B", primaryTint="#E7F0EA", accent="#F2B705"),
)


async def get_party_settings() -> Branding | None:
    return _DEMO
# -------------------------------------------------------------------------


@router.get("/branding", response_model=Branding)
async def branding() -> Branding:
    b = await get_party_settings()
    if b is None:
        raise HTTPException(status_code=404, detail="PartySettings not configured")
    return b

# Contrast rule for the CRM "Branding" screen (Website content → Branding):
# reject a primary colour whose contrast with white text is below 4.5:1, and an
# accent whose contrast with ink #13201A is below 4.5:1, so a party can't make
# its own buttons unreadable.
