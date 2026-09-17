"""The strategy read."""

from pydantic import BaseModel


class UnitRead(BaseModel):
    unit: str
    needed: int
    committed: int
    gap: int
    progress: float
    events: int
    has_mobilizer: bool
    share: float = 0.0


class NoteRead(BaseModel):
    tone: str
    title: str
    text: str


class StrategyRead(BaseModel):
    win_number: int
    committed: int
    progress_pct: float
    total_registered: int
    total_cast: int
    units: list[UnitRead]
    notes: list[NoteRead]
