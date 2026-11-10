"""Refusals the services raise; the API answers them as 400, 403 for Forbidden, 404 for NotFound."""

# What a uniqueness rule answers, both before an insert and when one races past.
PHONE_ON_REGISTER = "That phone number is already on this campaign's register."
LIVE_NOMINATION = "That member already has a live nomination."
HAS_WORKSPACE = "That aspirant already has a workspace."


class Refused(Exception):
    """A request that cannot be done, with the reason to show."""


class NotFound(Refused):
    """The named row does not exist."""


class Forbidden(Refused):
    """The caller may not do this."""


class TooLarge(Refused):
    """The upload is over its type's size limit."""


class CampaignClosed(Exception):
    """The caller's campaign is closed while its aspirant is not approved."""

    code = "campaign_suspended"


def refuse_own_record(actor, member_id) -> None:  # type: ignore[no-untyped-def]
    """Forbidden when the acting officer's login belongs to this party member.

    The superuser is exempt.
    """
    if actor is None or actor.is_superuser:
        return
    if actor.party_member_id is not None and actor.party_member_id == member_id:
        raise Forbidden("You cannot act on your own party record.")


def refuse_erased(row) -> None:  # type: ignore[no-untyped-def]
    """Refused when the person's details on this row were erased."""
    if row.erased_at is not None:
        raise Refused("This person's details were erased.")


def refuse_unlisted_move(moves: dict, frm, to, noun: str) -> None:  # type: ignore[no-untyped-def]
    """Refused when the move table does not list `frm` to `to`."""
    if to not in moves[frm]:
        raise Refused(f"A {frm.label.lower()} {noun} cannot be moved to {to.label.lower()}.")
