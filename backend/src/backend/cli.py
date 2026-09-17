"""campaign-crm: load reference data, seed the demo, and run the admin operations."""

import argparse
import asyncio
import getpass
import sys
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_engine, get_sessionmaker
from backend.models import County, UserRole
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
from backend.services.accounts import new_login
from backend.services.errors import Refused


async def _seed(args: argparse.Namespace, session: AsyncSession) -> int:
    if await session.scalar(select(County).limit(1)) is not None and not args.force:
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
    if not centres_csv.exists():
        print(f"No {centres_csv.name} found, so ward (MCA) campaigns have no centres to target.")
        return 0
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
    password = args.password or getpass.getpass("Password: ")
    if not password:
        print("A password is required.", file=sys.stderr)
        return 1
    user, _ = await new_login(
        session,
        username=args.username,
        role=UserRole(args.role),
        password=password,
        email=args.email,
        first_name=args.first_name,
        last_name=args.last_name,
        phone=args.phone,
        is_superuser=args.superuser,
    )
    await session.commit()
    print(f"Created {user}.")
    return 0


async def _campaign(args: argparse.Namespace, session: AsyncSession) -> int:
    """Every campaign with its candidate, or one campaign in full with -c."""
    if args.campaign is None:
        found = await admin.campaigns(session)
        for row in found:
            candidate = row.candidate or "-- none --"
            print(f"{row.id}  {row.title}  candidate {candidate}  members {len(row.members)}")
        if not found:
            print("No campaigns.")
        return 0

    row = await admin.campaign(session, args.campaign)
    print(row.title)
    print(f"  id         {row.id}")
    print(f"  seat       {row.office_level}")
    print(f"  candidate  {row.candidate or '-- none --'}")
    print(f"  election   {row.election_date or 'not set'}")
    print("  team")
    for member in row.members:
        print(f"    {member.role.value:10} {member.username}")
    print(f"  targets    {row.targets}")
    print(f"  mobilizers {row.mobilizers}")
    print(f"  events     {row.events}")
    print(f"  supporters {row.supporters}")
    print(f"  votes      {row.votes_needed:,} needed, {row.votes_committed:,} committed")
    return 0


async def _users(args: argparse.Namespace, session: AsyncSession) -> int:
    """Every login, its role, and the campaign it is on."""
    role = UserRole(args.role) if args.role else None
    people = await admin.users(session, role=role, campaign_id=args.campaign)
    for user in people:
        flags = ("" if user.is_active else "  [disabled]") + (
            "  [superuser]" if user.is_superuser else ""
        )
        seen = user.last_login_at[:10] if user.last_login_at else "never"
        print(f"{user.username:20} {user.role.value:10} last in {seen}{flags}")
        print(f"    {user.campaign or 'on no campaign'}")
    if not people:
        print("No users.")
    return 0


async def _reset_password(args: argparse.Namespace, session: AsyncSession) -> int:
    user = await admin.user_by_name(session, args.username)
    password = await admin.reset_password(session, user.id, args.password)
    print(f"{args.username} signs in with: {password}")
    print("Shown once, and every other session is signed out.")
    return 0


async def _add_member(args: argparse.Namespace, session: AsyncSession) -> int:
    user = await admin.user_by_name(session, args.username)
    member = await admin.add_member(session, args.campaign, user.id)
    print(f"{args.username} is on that campaign as its {member.role.label.lower()}.")
    return 0


async def _remove_member(args: argparse.Namespace, session: AsyncSession) -> int:
    user = await admin.user_by_name(session, args.username)
    await admin.remove_member(session, args.campaign, user.id)
    print(f"{args.username} is off that campaign.")
    return 0


async def _rename_campaign(args: argparse.Namespace, session: AsyncSession) -> int:
    campaign = await admin.rename_campaign(session, args.campaign, args.title)
    print(f"The campaign is now called {campaign.title}.")
    return 0


async def _delete_campaign(args: argparse.Namespace, session: AsyncSession) -> int:
    """Without --yes, only say what and who would be deleted."""
    row = await admin.campaign(session, args.campaign)
    people = await admin.logins_on(session, args.campaign)
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
    user = await admin.user_by_name(session, args.username)
    await admin.set_active(session, user.id, args.active)
    print(f"{args.username} is {'enabled' if args.active else 'disabled'}.")
    return 0


Handler = Callable[[argparse.Namespace, AsyncSession], Awaitable[int]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="campaign-crm", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def command(name: str, handler: Handler, help_text: str, **defaults) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, help=help_text)
        sub.set_defaults(handler=handler, **defaults)
        return sub

    def needs_user(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("-u", "--username", required=True)

    def needs_campaign(sub: argparse.ArgumentParser, required: bool = True) -> None:
        sub.add_argument("-c", "--campaign", required=required, type=uuid.UUID, help="campaign id")

    seed = command("seed", _seed, "load the bundled 2022 reference data")
    seed.add_argument("--caw", default=str(CAW_CSV), help="wards and their registered voters")
    seed.add_argument("--county-voters", default=str(COUNTY_VOTERS_CSV))
    seed.add_argument("--county-results", default=str(COUNTY_RESULTS_CSV))
    seed.add_argument("--centres", default=str(CENTRES_CSV))
    seed.add_argument("--force", action="store_true", help="reload even if data is present")

    demo = command("demo", _demo, "build the demo campaign and its sign-ins")
    demo.add_argument("-p", "--password", help="one password for every demo account")

    createuser = command("createuser", _createuser, "add a login")
    needs_user(createuser)
    createuser.add_argument(
        "-r", "--role", default=UserRole.MANAGER.value, choices=[r.value for r in UserRole]
    )
    createuser.add_argument("-p", "--password", help="prompted for when left out")
    createuser.add_argument("--email", default="")
    createuser.add_argument("--first-name", default="")
    createuser.add_argument("--last-name", default="")
    createuser.add_argument("--phone", default="")
    createuser.add_argument("--superuser", action="store_true")

    needs_campaign(
        command("campaign", _campaign, "every campaign, or one in full with -c"), required=False
    )

    users = command("users", _users, "every login and the campaign it is on")
    users.add_argument("-r", "--role", choices=[r.value for r in UserRole])
    needs_campaign(users, required=False)

    reset = command("reset-password", _reset_password, "give a login a new password")
    needs_user(reset)
    reset.add_argument("-p", "--password", help="generated when left out")

    for name, handler, help_text in (
        ("add-member", _add_member, "put somebody on a campaign"),
        ("remove-member", _remove_member, "take somebody off a campaign"),
    ):
        sub = command(name, handler, help_text)
        needs_user(sub)
        needs_campaign(sub)

    rename = command("rename-campaign", _rename_campaign, "change what a campaign is called")
    needs_campaign(rename)
    rename.add_argument("-t", "--title", required=True)

    drop = command(
        "delete-campaign", _delete_campaign, "delete a campaign, everything on it, and its logins"
    )
    needs_campaign(drop)
    drop.add_argument("--yes", action="store_true", help="delete it, rather than only saying what")

    needs_user(command("deactivate", _set_active, "stop a login working", active=False))
    needs_user(command("activate", _set_active, "let a disabled login work again", active=True))
    return parser


async def run(args: argparse.Namespace, session: AsyncSession) -> int:
    """Run the parsed command; a refusal prints to stderr and exits 1."""
    try:
        return await args.handler(args, session)
    except Refused as error:
        print(error, file=sys.stderr)
        return 1


async def _run(args: argparse.Namespace) -> int:
    try:
        async with get_sessionmaker()() as session:
            return await run(args, session)
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
