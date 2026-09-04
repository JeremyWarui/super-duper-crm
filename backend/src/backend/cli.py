"""Command line jobs: load the reference data, build the demo, add a user.

uv run campaign-crm seed          # geography, then centres if the CSV is there
uv run campaign-crm demo          # the worked campaign and its three sign-ins
uv run campaign-crm createuser -u amina -r manager
"""

import argparse
import asyncio
import getpass
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_engine, get_sessionmaker
from backend.models import County, User, UserRole
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
        print(f"  {centres.centres} centres across {centres.wards_covered} wards.")
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
