"""What each campaign role may do, and how far it reaches (docs/Product_Design.md, section 0.2).

`all` is the whole campaign, `area` the coordinator's wards and centres, `own` the caller's own
rows (a mobilizer's ward). A role missing from an action may not do it. In the party workspace
the Workspace Manager holds the Manager column.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import ColumnElement, Select, false, or_

from backend.models import User, UserRole


class Reach(StrEnum):
    ALL = "all"
    AREA = "area"
    OWN = "own"


R = UserRole
ALL, AREA, OWN = Reach.ALL, Reach.AREA, Reach.OWN

MAP: dict[str, dict[UserRole, Reach]] = {
    "strategy.read": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA},
    "targets.read": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA, R.MOBILIZER: OWN},
    "targets.write": {R.CANDIDATE: ALL, R.MANAGER: ALL},
    "team.manager": {R.CANDIDATE: ALL},
    "team.write": {R.CANDIDATE: ALL, R.MANAGER: ALL},
    "team.approve": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA},
    "team.id_read": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.MOBILIZER: OWN, R.AGENT: OWN},
    "agents.read": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA, R.AGENT: OWN},
    "agents.write": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA},
    "mobilizers.read": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA, R.MOBILIZER: OWN},
    "mobilizers.write": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA},
    "supporters.read": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA, R.MOBILIZER: OWN},
    "supporters.write": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA, R.MOBILIZER: OWN},
    "events.read": {
        R.CANDIDATE: ALL,
        R.MANAGER: ALL,
        R.COORDINATOR: AREA,
        R.COMMS: ALL,
        R.MOBILIZER: OWN,
        R.AGENT: OWN,
    },
    "events.write": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA, R.MOBILIZER: OWN},
    "payments.read": {
        R.CANDIDATE: ALL,
        R.MANAGER: ALL,
        R.COORDINATOR: AREA,
        R.MOBILIZER: OWN,
        R.AGENT: OWN,
    },
    "payments.schedule": {R.MANAGER: ALL, R.COORDINATOR: AREA},
    # Which of them approves a given payment: services/payment_routing.py (decision 27).
    "payments.approve": {R.CANDIDATE: ALL, R.MANAGER: ALL},
    "assignments.read": {
        R.CANDIDATE: ALL,
        R.MANAGER: ALL,
        R.COORDINATOR: AREA,
        R.MOBILIZER: OWN,
        R.AGENT: OWN,
    },
    "assignments.write": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA},
    # Writing a text to supporters; a Coordinator's reaches only their area.
    "sms.draft": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA, R.COMMS: ALL},
    # Really texting: approving a draft, or an event invitation that is not a dry run.
    "sms.send": {R.CANDIDATE: ALL, R.MANAGER: ALL},
    # Aspirant installations: the website and its settings.
    "site.write": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COMMS: ALL},
    "volunteers.read": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA},
    "volunteers.write": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COORDINATOR: AREA},
    "export": {R.CANDIDATE: ALL, R.MANAGER: ALL},
    # A hosted workspace's "From the party" page, and the counts it shares with the party.
    "party.feed": {R.CANDIDATE: ALL, R.MANAGER: ALL, R.COMMS: ALL},
    "sharing.write": {R.CANDIDATE: ALL},
    # Data requests, erasure on request, and the withdrawal links of supporters.
    "data.manage": {R.CANDIDATE: ALL, R.MANAGER: ALL},
    # Closing the campaign after the election, and erasing its supporters after retention.
    "campaign.close": {R.CANDIDATE: ALL},
    # Contributions paid in from the website, and confirming the M-Pesa codes payers report.
    "contributions.read": {R.CANDIDATE: ALL, R.MANAGER: ALL},
}

REFUSALS = {
    "team.manager": "Only the aspirant adds or replaces the campaign manager.",
    "team.write": "Only a candidate or a campaign manager may add or remove people.",
    "team.approve": "Only the candidate, the manager or a coordinator decides team sign-ups.",
    "mobilizers.write": "Only the candidate, the manager or a coordinator may change mobilizers.",
    "supporters.read": "The supporter register is for the campaign team.",
    "supporters.write": "The supporter register is for the campaign team.",
    "sms.send": "Only the candidate or the campaign manager sends texts.",
    "sharing.write": "Only the candidate decides what the campaign shares with the party.",
    "data.manage": "Only the candidate or the campaign manager handles personal data requests.",
    "campaign.close": "Only the candidate closes the campaign.",
    "contributions.read": "Only the candidate or the campaign manager sees contributions.",
}


def reach(user: User, action: str) -> Reach | None:
    """How far this login reaches with the action; None when it may not do it."""
    if user.role is None:
        return None
    return MAP[action].get(user.role)


def refusal(user: User, action: str) -> str:
    if user.role is None:
        return "This login has no campaign role."
    return REFUSALS.get(action, f"A {user.role.label} may not do this.")


@dataclass(frozen=True)
class Area:
    """The wards and registration centres a caller reaches; a row in either is inside."""

    wards: frozenset[uuid.UUID]
    centres: frozenset[uuid.UUID]

    def holds(self, ward_id: uuid.UUID | None, centre_id: uuid.UUID | None = None) -> bool:
        return ward_id in self.wards or (centre_id is not None and centre_id in self.centres)

    def where(self, ward: ColumnElement, centre: ColumnElement | None = None) -> ColumnElement:
        clauses = [ward.in_(self.wards)] if self.wards else []
        if centre is not None and self.centres:
            clauses.append(centre.in_(self.centres))
        return or_(*clauses) if clauses else false()


def narrow(statement: Select, area: Area | None, model: type) -> Select:
    """Keep `model`'s rows inside `area` by their ward and, when it has one, their centre; no
    area keeps every row."""
    if area is None:
        return statement
    return statement.where(
        area.where(model.ward_id, getattr(model, "registration_centre_id", None))
    )
