"""Who approves a payment (decision 27): whoever schedules one never approves it.

A coordinator's payment goes to the manager; a manager's to the candidate. The candidate never
schedules.
"""

from backend.models import Payment, User, UserRole
from backend.services.errors import Refused


def approver_for(scheduler: User) -> UserRole:
    """The role that approves a payment this caller schedules; refused when they may not."""
    if scheduler.role is UserRole.COORDINATOR:
        return UserRole.MANAGER
    if scheduler.role is UserRole.MANAGER:
        return UserRole.CANDIDATE
    raise Refused("Only a coordinator or the manager schedules payments.")


def approver_of(payment: Payment) -> UserRole:
    """A payment from before routing is the manager's to approve."""
    return payment.approver_role or UserRole.MANAGER


def may_approve(user: User, payment: Payment) -> bool:
    return user.role is approver_of(payment) and payment.scheduled_by_id != user.id
