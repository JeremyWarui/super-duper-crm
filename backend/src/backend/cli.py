"""Command line jobs: loading data, and running the campaigns on this deployment.

The administration commands are the same operations `/api/admin/` serves,
through `backend.services.admin`, so the two cannot drift. The command line
is how the first superuser is made, and how the deployment is reached when
the console cannot be.
"""

import argparse
import asyncio
import getpass
import sys
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_engine, get_sessionmaker
from backend.models import Campaign, CampaignMember, County, User, UserRole
from backend.security import hash_password
from backend.seed.demo import seed_demo
from backend.seed.reference import (
    CAW_CSV,
    CENTRES_CSV,
    COUNTY_RESULTS_CSV,
    COUNTY_VOTERS_CSV,
    import_centres,
    import_geography,
)
from backend.services import admin


async def _seed(args: argparse.Namespace, session: AsyncSession) -> int:
    already = (await session.execute(select(County).limit(1))).scalar_one_or_none()
    if already is not None and not args.force:
        print("Reference data is already loaded. Pass --force to reload it.")
        return 0

    print("Loading geography...")
    geography = await import_geography(
        session,
        caw=Path(args.caw),
        county_voters=Path(args.county_voters),
        county_results=Path(args.county_results),
    )
    print(
        f"  {geography.counties} counties, {geography.constituencies} constituencies, "
        f"{geography.wards} wards. Turnout set for {geography.turnout_set} counties."
    )

    centres_csv = Path(args.centres)
    if centres_csv.exists():
        print("Loading registration centres...")
        centres = await import_centres(session, centres_csv)
        print(f"  {centres.centres:,} centres across {centres.wards_covered:,} wards.")
        if centres.skipped_special:
            print(
                f"  {centres.skipped_special:,} diaspora and prison rows left out: "
                "neither sits in a ward."
            )
        if centres.unmatched:
            print(f"  {len(centres.unmatched)} rows matched no ward, e.g. {centres.unmatched[:3]}")
    else:
        print(f"No {centres_csv.name} found, so ward (MCA) campaigns have no centres to target.")
    return 0


async def _demo(args: argparse.Namespace, session: AsyncSession) -> int:
    summary = await seed_demo(session, password=args.password)
    print(f"{summary.campaign_title} - {summary.office}")
    print(f"  {summary.units} units, win number {summary.win_number:,}")
    print("\nSign in at http://localhost:5173 as (shown once, re-run to reset):")
    width = max(len(username) for username, _, _ in summary.sign_ins)
    for username, password, description in summary.sign_ins:
        print(f"  {username:<{width}}  {password:<20}  {description}")
    return 0


async def _createuser(args: argparse.Namespace, session: AsyncSession) -> int:
    existing = (
        await session.execute(select(User).where(User.username == args.username))
    ).scalar_one_or_none()
    if existing is not None:
        print(f"{args.username} already exists.", file=sys.stderr)
        return 1

    password = args.password or getpass.getpass("Password: ")
    if not password:
        print("A password is required.", file=sys.stderr)
        return 1

    user = User(
        username=args.username,
        role=UserRole(args.role),
        email=args.email,
        first_name=args.first_name,
        last_name=args.last_name,
        phone=args.phone,
        password_hash=hash_password(password),
        is_superuser=args.superuser,
    )
    session.add(user)
    await session.commit()
    print(f"Created {user}.")
    return 0


async def _campaigns(args: argparse.Namespace, session: AsyncSession) -> int:
    """Every campaign with its candidate and everyone on it, so gaps are visible."""
    rows = (
        await session.execute(
            select(Campaign).options(
                selectinload(Campaign.candidate),
                selectinload(Campaign.members).selectinload(CampaignMember.user),
            )
        )
    ).scalars()

    listed = 0
    for campaign in sorted(rows, key=lambda c: c.created_at):
        managers = [m.user.username for m in campaign.members if m.role is UserRole.MANAGER]
        print(f"{campaign.id}  {campaign.title}")
        print(
            f"    candidate {campaign.candidate.username if campaign.candidate else '-- none --'}"
            f"    managers {', '.join(managers) or '-- none --'}"
            f"    members {len(campaign.members)}"
        )
        listed += 1
    if listed == 0:
        print("No campaigns.")
    return 0


async def _assign_manager(args: argparse.Namespace, session: AsyncSession) -> int:
    """Put a manager on a campaign, which is what makes it visible to them."""
    campaign = await session.get(Campaign, args.campaign)
    if campaign is None:
        print(f"No campaign with id {args.campaign}.", file=sys.stderr)
        return 1

    user = (
        await session.execute(select(User).where(User.username == args.username))
    ).scalar_one_or_none()
    if user is None:
        print(f"No user called {args.username}.", file=sys.stderr)
        return 1
    if user.role is not UserRole.MANAGER:
        print(f"{args.username} is a {user.role.label}, not a campaign manager.", file=sys.stderr)
        return 1

    if args.only:
        await session.execute(
            delete(CampaignMember).where(
                CampaignMember.campaign_id == campaign.id,
                CampaignMember.role == UserRole.MANAGER,
                CampaignMember.user_id != user.id,
            )
        )

    try:
        await admin.add_member(session, campaign.id, user.id)
    except admin.AdminError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{args.username} now runs {campaign.title}.")
    return 0


async def _users(args: argparse.Namespace, session: AsyncSession) -> int:
    """Every login, what it is, and which campaigns it reaches."""
    role = UserRole(args.role) if args.role else None
    people = await admin.users(session, role=role, campaign_id=args.campaign)
    if not people:
        print("No users.")
        return 0

    for user in people:
        flags = "" if user.is_active else "  [disabled]"
        flags += "  [superuser]" if user.is_superuser else ""
        seen = user.last_login_at[:10] if user.last_login_at else "never"
        print(f"{user.username:20} {user.role.value:10} last in {seen}{flags}")
        for _, title, place in user.campaigns:
            print(f"    {place.value:10} {title}")
        if not user.campaigns:
            print("    on no campaign")
    return 0


async def _campaign(args: argparse.Namespace, session: AsyncSession) -> int:
    """One campaign: who is on it, and how much of it exists."""
    found = await admin.campaigns(session, args.campaign)
    if not found:
        print(f"No campaign with id {args.campaign}.", file=sys.stderr)
        return 1

    row = found[0]
    print(row.title)
    print(f"  id         {row.id}")
    print(f"  seat       {row.office_level}")
    print(f"  candidate  {row.candidate or '-- none --'}")
    print(f"  election   {row.election_date or 'not set'}")
    print("  team")
    for member in row.members:
        print(f"    {member.role.value:10} {member.username}")
    if not row.members:
        print("    nobody")
    print(f"  targets    {row.targets}")
    print(f"  mobilizers {row.mobilizers}")
    print(f"  events     {row.events}")
    print(f"  supporters {row.supporters}")
    print(f"  votes      {row.votes_needed:,} needed, {row.votes_committed:,} committed")
    return 0


async def _reset_password(args: argparse.Namespace, session: AsyncSession) -> int:
    """Give a login a new password. The only way back in from a lost one."""
    people = await admin.users(session)
    user = next((u for u in people if u.username == args.username), None)
    if user is None:
        print(f"No user called {args.username}.", file=sys.stderr)
        return 1

    try:
        password = await admin.reset_password(session, user.id, args.password)
    except admin.AdminError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{args.username} signs in with: {password}")
    print("Shown once, and every other session is signed out.")
    return 0


async def _add_member(args: argparse.Namespace, session: AsyncSession) -> int:
    """Put anybody back on a campaign, in the capacity their login carries."""
    people = await admin.users(session)
    user = next((u for u in people if u.username == args.username), None)
    if user is None:
        print(f"No user called {args.username}.", file=sys.stderr)
        return 1

    try:
        member = await admin.add_member(session, args.campaign, user.id)
    except admin.AdminError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{args.username} is on that campaign as its {member.role.label.lower()}.")
    return 0


async def _remove_member(args: argparse.Namespace, session: AsyncSession) -> int:
    """Take somebody off a campaign. Their login and their work stay."""
    people = await admin.users(session)
    user = next((u for u in people if u.username == args.username), None)
    if user is None:
        print(f"No user called {args.username}.", file=sys.stderr)
        return 1

    try:
        await admin.remove_member(session, args.campaign, user.id)
    except admin.AdminError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{args.username} is off that campaign.")
    return 0


async def _rename_campaign(args: argparse.Namespace, session: AsyncSession) -> int:
    """Change what a campaign is called."""
    try:
        campaign = await admin.rename_campaign(session, args.campaign, args.title)
    except admin.AdminError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"The campaign is now called {campaign.title}.")
    return 0


async def _delete_campaign(args: argparse.Namespace, session: AsyncSession) -> int:
    """Delete a campaign, everything on it and its logins. Without --yes, only say what would go."""
    found = await admin.campaigns(session, args.campaign)
    if not found:
        print(f"No campaign with id {args.campaign}.", file=sys.stderr)
        return 1
    row = found[0]
    people = await admin.logins_deleted_with(session, args.campaign)
    logins = ", ".join(person.username for person in people) or "none"
    what = (
        f"{row.title} with {row.targets} targets, {row.mobilizers} mobilizers, "
        f"{row.events} events, {row.supporters} supporters, and {len(people)} logins "
        f"({logins})"
    )
    if not args.yes:
        print(f"This would delete {what}. Run it again with --yes.", file=sys.stderr)
        return 1

    gone = await admin.delete_campaign(session, args.campaign)
    print(f"Deleted {row.title} and {len(gone)} logins: {', '.join(gone) or 'none'}.")
    return 0


async def _set_active(args: argparse.Namespace, session: AsyncSession) -> int:
    """Turn a login off or on. Off refuses a new sign-in and drops the live token."""
    people = await admin.users(session)
    user = next((u for u in people if u.username == args.username), None)
    if user is None:
        print(f"No user called {args.username}.", file=sys.stderr)
        return 1

    try:
        await admin.set_active(session, user.id, args.active)
    except admin.AdminError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{args.username} is {'enabled' if args.active else 'disabled'}.")
    return 0


Handler = Callable[[argparse.Namespace, AsyncSession], Awaitable[int]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="campaign-crm", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed = subparsers.add_parser("seed", help="load the bundled 2022 reference data")
    seed.add_argument("--caw", default=str(CAW_CSV), help="wards and their registered voters")
    seed.add_argument("--county-voters", default=str(COUNTY_VOTERS_CSV))
    seed.add_argument("--county-results", default=str(COUNTY_RESULTS_CSV))
    seed.add_argument("--centres", default=str(CENTRES_CSV))
    seed.add_argument("--force", action="store_true", help="reload even if data is present")
    seed.set_defaults(handler=_seed)

    demo = subparsers.add_parser("demo", help="build the demo campaign and its three sign-ins")
    demo.add_argument(
        "-p", "--password", help="use this for all three accounts; generated per account otherwise"
    )
    demo.set_defaults(handler=_demo)

    createuser = subparsers.add_parser("createuser", help="add a user who can sign in")
    createuser.add_argument("-u", "--username", required=True)
    createuser.add_argument(
        "-r", "--role", default=UserRole.MANAGER.value, choices=[r.value for r in UserRole]
    )
    createuser.add_argument("-p", "--password", help="prompted for when left out")
    createuser.add_argument("--email", default="")
    createuser.add_argument("--first-name", default="")
    createuser.add_argument("--last-name", default="")
    createuser.add_argument("--phone", default="")
    createuser.add_argument("--superuser", action="store_true")
    createuser.set_defaults(handler=_createuser)

    campaigns = subparsers.add_parser(
        "campaigns", help="list every campaign, its candidate and its manager"
    )
    campaigns.set_defaults(handler=_campaigns)

    assign = subparsers.add_parser(
        "assign-manager", help="put a manager on a campaign, so they can see it"
    )
    assign.add_argument("-u", "--username", required=True)
    assign.add_argument("-c", "--campaign", required=True, type=uuid.UUID, help="campaign id")
    assign.add_argument("--only", action="store_true", help="take every other manager off it")
    assign.set_defaults(handler=_assign_manager)

    campaign = subparsers.add_parser("campaign", help="one campaign: its team and its size")
    campaign.add_argument("-c", "--campaign", required=True, type=uuid.UUID, help="campaign id")
    campaign.set_defaults(handler=_campaign)

    users = subparsers.add_parser("users", help="every login and the campaigns it reaches")
    users.add_argument("-r", "--role", choices=[r.value for r in UserRole])
    users.add_argument("-c", "--campaign", type=uuid.UUID, help="only people on this campaign")
    users.set_defaults(handler=_users)

    reset = subparsers.add_parser("reset-password", help="give a login a new password")
    reset.add_argument("-u", "--username", required=True)
    reset.add_argument("-p", "--password", help="generated when left out")
    reset.set_defaults(handler=_reset_password)

    add = subparsers.add_parser("add-member", help="put somebody on a campaign")
    add.add_argument("-u", "--username", required=True)
    add.add_argument("-c", "--campaign", required=True, type=uuid.UUID, help="campaign id")
    add.set_defaults(handler=_add_member)

    remove = subparsers.add_parser("remove-member", help="take somebody off a campaign")
    remove.add_argument("-u", "--username", required=True)
    remove.add_argument("-c", "--campaign", required=True, type=uuid.UUID, help="campaign id")
    remove.set_defaults(handler=_remove_member)

    rename = subparsers.add_parser("rename-campaign", help="change what a campaign is called")
    rename.add_argument("-c", "--campaign", required=True, type=uuid.UUID, help="campaign id")
    rename.add_argument("-t", "--title", required=True)
    rename.set_defaults(handler=_rename_campaign)

    drop = subparsers.add_parser(
        "delete-campaign", help="delete a campaign, everything on it, and its people's logins"
    )
    drop.add_argument("-c", "--campaign", required=True, type=uuid.UUID, help="campaign id")
    drop.add_argument("--yes", action="store_true", help="delete it, rather than only saying what")
    drop.set_defaults(handler=_delete_campaign)

    disable = subparsers.add_parser("deactivate", help="stop a login working, keeping its rows")
    disable.add_argument("-u", "--username", required=True)
    disable.set_defaults(handler=_set_active, active=False)

    enable = subparsers.add_parser("activate", help="let a disabled login work again")
    enable.add_argument("-u", "--username", required=True)
    enable.set_defaults(handler=_set_active, active=True)

    return parser


async def _run(args: argparse.Namespace) -> int:
    handler: Handler = args.handler
    try:
        async with get_sessionmaker()() as session:
            return await handler(args, session)
    finally:
        await get_engine().dispose()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except (ValueError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
