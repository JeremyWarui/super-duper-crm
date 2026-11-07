"""Refusals the services raise; the API answers them as 400, 403 for Forbidden, 404 for NotFound."""


class Refused(Exception):
    """A request that cannot be done, with the reason to show."""


class NotFound(Refused):
    """The named row does not exist."""


class Forbidden(Refused):
    """The caller may not do this."""


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


class TwoStepNeeded(Exception):
    """The caller's login needs 2-step sign-in and this session has not passed it."""

    code = "two_step_required"
