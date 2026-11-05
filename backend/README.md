# Campaign CRM - backend

FastAPI, SQLAlchemy 2.0 (async) and Pydantic v2, on Postgres (Neon in production). Managed with `uv`.

## Quick start

Needs a local Postgres running.

```bash
cd backend
uv sync --group dev
createdb campaign_crm
cp .env.example .env                      # fill in SECRET_KEY and your Postgres password
uv run alembic upgrade head               # create the tables
uv run campaign-crm seed                  # load the 2022 geography
uv run campaign-crm demo                  # the demo campaign and its logins
uv run watchfiles "uvicorn backend.main:app" src .env   # http://127.0.0.1:8000/docs
```

`watchfiles` restarts the server on a change to `src` or `.env`; on Windows,
`uvicorn --reload` prints `Reloading...` and keeps serving the old code.

Checks:

```bash
uv run pytest        # tests and evals, no database server needed
uv run ruff check .
uv run ruff format .
```

## Command line

```bash
uv run campaign-crm seed                          # geography and centres; --force to reload
uv run campaign-crm demo [--password <shared>]    # the demo campaign; re-run to reset it
uv run campaign-crm createuser -u root -r manager --superuser
uv run campaign-crm campaign [-c <campaign id>]   # every campaign, or one in full
uv run campaign-crm users [-r role] [-c <id>]     # logins and the campaign each is on
uv run campaign-crm add-member -u amina -c <id>
uv run campaign-crm remove-member -u juma -c <id>
uv run campaign-crm rename-campaign -c <id> -t "Jane for Roysambu"
uv run campaign-crm delete-campaign -c <id>       # says what and who would go; add --yes
uv run campaign-crm reset-password -u jane
uv run campaign-crm deactivate -u jane            # and activate
uv run campaign-crm reset-database --yes <name>   # empty a Postgres database; see DEPLOY.md
```

The admin commands run the same service as the admin console. A refusal prints
its reason and exits 1.

`seed` loads the IEBC 2022 register from `data/`: 47 counties, 290
constituencies, 1450 wards and 27,273 registration centres, with each county's
turnout. Ward names from the gazetted register and the centres file are matched
after folding punctuation, and a clipped name matches when only one ward fits.
Diaspora (48) and prison (49) rows are skipped.

`demo` builds the Roysambu MP campaign with mobilizers, events and supporters on
some wards, and prints three logins, generated per run unless `--password` or
`DEFAULT_USER_PASSWORD` is set:

```
  aspirant     Candidate: the cockpit, adds mobilizers
  manager      Campaign manager: the full war room
  mobilizer    Mobilizer: one ward
```

`DEFAULT_USER_PASSWORD` gives every login the app creates the same password.
Leave it blank anywhere real.

## Layout

```
backend/
├── alembic/               the migration
├── data/                  the 2022 reference CSVs
├── src/backend/
│   ├── main.py            the app
│   ├── config.py          settings from the environment
│   ├── security.py        password hashing and token keys
│   ├── cli.py             campaign-crm
│   ├── api/
│   │   ├── deps.py        the session, the caller, role guards
│   │   ├── errors.py      one "detail" sentence per error
│   │   ├── scope.py       the caller's campaign and, for a mobilizer, ward
│   │   └── routers/       one module per resource
│   ├── db/                declarative base and session
│   ├── models/            the tables
│   ├── schemas/           request and response shapes
│   ├── seed/              the CSV loaders and the demo
│   └── services/          logins, targets, strategy, SMS, and the admin operations
├── tests/
└── evals/                 the contract with the SPA
```

## The API

Everything is under `/api`, with a trailing slash, and needs
`Authorization: Token <key>` unless noted.

| Route | What it does |
|---|---|
| `POST /api/auth/login/` `…/logout/` | Username and password for a token; sign out. |
| `GET /api/counties/` `…/{id}/`, `/api/constituencies/`, `/api/wards/`, `/api/centres/` | Reference geography; a mobilizer sees one ward. |
| `GET /api/campaigns/` `…/{id}/` | The caller's campaign. |
| `POST /api/campaigns/{id}/generate_targets/` | Rebuild the targets after new data. |
| `GET POST /api/campaigns/{id}/signups/` | The campaign-wide sign-up link: its code, and opening or closing it; manager only. |
| `GET POST /api/join/{code}/` | No token. The public sign-up page behind an event's QR code or a campaign's link. |
| `POST /api/join/withdraw/{code}/` | No token. A supporter takes their details off the register; the same answer for any code. |
| `GET POST /api/targets/`, `PATCH DELETE …/{id}/` | The win number per unit. |
| `GET POST /api/mobilizers/`, `DELETE …/{id}/` | Who works which ward. |
| `GET POST /api/events/`, `DELETE …/{id}/`, `POST …/{id}/record/`, `…/{id}/invite/` | Events, attendance, SMS invitations. |
| `GET POST /api/supporters/`, `PATCH …/{id}/` | The supporter register, and placing someone at a centre. Nobody on the team deletes a supporter; they withdraw themselves. |
| `GET /api/strategy/?campaign=` | The computed dashboard. |
| `POST /api/users/`, `DELETE …/{id}/` | Mobilizer logins; the password is returned once. |
| `/api/admin/…` | The console; superusers only. |

A foreign key travels under the bare name (`ward`, not `ward_id`), and reads
carry the parent's name beside it. Every error is `{"detail": "<sentence>"}`.

### By organisation type

`site_settings.organisation_type` decides what exists. In an aspirant
installation the party office (`/api/party/members/`, `…/volunteers/`,
`…/aspirants/`, the dashboard and console), the party's own website pages
(leaders, organs, values, branches, results, join and withdraw, the candidates
directory) and their console editors answer 404, as if they were never
mounted. The website content both types share (posts, slides, issues,
documents, videos, places, subscribe, contribute) stays under `/api/party/`.
Party-only routes are `PartyOnlyRoute`s (`api/install.py`): the routers that
mix both kinds put them on a `party_router`. The `InstallationType`
middleware reads the type for any request shaped like a party route, and a
`PartyOnlyRoute` matches nothing outside a party installation, so any method,
body or missing slash gets the same 404 as an unknown path. The party inbox
task runs only in a party installation.

Campaign workspace access is decided in `services/access.py`: party and
standalone workspaces are always open; a hosted one is open while its aspirant
is approved, or when it has none.

The party workspace (`kind = 'party'`, national, no seat or candidate) is
created once by a superuser (`POST /api/party/workspace/`) with its first
Workspace Manager, and gets a target in every ward. Its coordinators read the
party members living in their area (`GET /api/party/workspace/members/`,
read-only, a page at a time, each page audited as `members.area_read`) and
hold one active recruitment code each (`…/recruitment/`; POST replaces it).
A Join the Party application carrying an active code records the coordinator
and the county of the applicant's ward; any other code is ignored, and
membership officers still decide every application. A coordinator of a
hosted workspace gets 404 on these routes. The dashboard counts the party
workspace apart from hosted ones.

A candidate page (`candidate_profiles`) belongs to a campaign, one each; a
hosted campaign's page also names its aspirant. A campaign's volunteers
(`models/volunteer.py`, `campaign_id` set) are read, moved, signed up and
withdrawn through `services/campaign_volunteers.py`; `services/volunteers.py`
handles the party's own.

## Rules

- **One campaign per login.** Every route that puts a login on a campaign
  refuses a second one, and a unique index on `campaign_members.user_id` refuses
  it in the database.
- **A campaign belongs to its candidate**, the member whose role is candidate; a
  partial unique index allows one.
- **Only a superuser creates a campaign**, from the console, with new logins for
  its aspirant and, optionally, its manager. Nobody signs up for a login.
- **A campaign runs its own team.** Its aspirant adds the one manager, or
  replaces them: the old manager comes off the campaign and their login is
  turned off. The aspirant and the manager add coordinators and comms
  officers (`POST /api/campaigns/{id}/team/`) and set a coordinator's wards and
  centres (`PUT …/team/{user}/area/`); they and a coordinator (in their area)
  add and remove mobilizers. A second manager is refused everywhere, the
  console included.
- **Only the superuser resets a password**, from the console or with
  `campaign-crm reset-password`. Nobody on a campaign resets a teammate's. A
  reset signs the person out.
- **In an MCA race a mobilizer works one registration centre with a target**,
  or none yet; a whole ward or an untargeted centre is refused.
- **Supporters sign themselves up and withdraw themselves.** `/api/join/{code}/`
  takes an event's code or the campaign's own link (`/api/campaigns/{id}/signups/`,
  which starts closed and only the candidate and manager read or open); the campaign link asks
  for a ward, or in an MCA race an optional centre, from the campaign. Every
  sign-up gets a withdrawal code, which only works for a new supporter, and
  `/api/join/withdraw/{code}/` answers the same for any code, so neither page
  shows whether a phone is on the register.
- **Only an admin deletes a campaign**, and that deletes everything on it and the
  logins of its people.
- **Scoping is by membership.** A campaign the caller is not on answers 404.
  Inside it, `services/permissions.py` maps each action to the roles that may do
  it and how far they reach: the whole campaign, a coordinator's area (their
  `campaign_member_areas` wards and centres), or a mobilizer's own ward. Routers
  guard with `require(action)` (`api/deps.py`); `api/scope.py` applies the reach
  to every read and write, and a place outside it answers 403.

| | Candidate | Manager | Coordinator | Comms | Mobilizer | Agent |
|---|---|---|---|---|---|---|
| Strategy | yes | yes | area | no | no | no |
| Read targets | yes | yes | area | no | own ward | no |
| Change targets | yes | yes | no | no | no | no |
| Add or replace the manager | yes | no | no | no | no | no |
| Team: coordinators, comms, areas | yes | yes | no | no | no | no |
| Read mobilizers | yes | yes | area | no | own ward | no |
| Add, move, remove mobilizers | yes | yes | area | no | no | no |
| Supporter register, read and write | yes | yes | area | no | own ward | no |
| Read events | yes | yes | area | yes | own ward | own |
| Schedule and record events, preview invites | yes | yes | area | no | own ward | no |
| Send event invites by SMS | yes | yes | no | no | own ward | no |
| Read payments | yes | yes | area | no | own | own |
| Schedule payments | no | yes | area | no | no | no |
| Release, cancel, mark payments | no | yes | no | no | no | no |
| Campaign volunteers | yes | yes | area | no | no | no |
| Delete a campaign, reach `/api/admin/` | no | no | no | no | no | no |

## The admin console

A superuser (`createuser --superuser`) gets `/api/admin/`: every campaign with
its team, wards and size; every login and its campaign; create a campaign with
new logins for its aspirant and manager (`POST /api/admin/campaigns/`, the only
way one is made); rename and delete a campaign; add and remove members; create a
login; reset a password; disable or enable a login. An admin cannot disable themselves or the last active superuser,
and a superuser is never put on a campaign.

## Invitations

`POST /api/events/{id}/invite/` texts an event's supporters, normalised to E.164
and deduplicated, and sets `number_reached` on a real delivery. `dry_run` works
out the recipients and cost without sending. Sending needs:

```bash
SMS_PROVIDER=africastalking
AT_USERNAME=your-username     # or "sandbox"
AT_API_KEY=<africas-talking-api-key>
AT_SENDER_ID=                 # blank uses the shared short code
```

Without it the console provider records the request and reports
`delivered: false`.

## Payouts

Releasing a campaign's mobilizer payment (`/api/payments/`) goes through the
payout provider. The
default, `practice`, moves no money and marks each release paid under a
`PRACTICE-` reference. Real M-Pesa transfers through Paystack need:

```bash
PAYOUT_PROVIDER=paystack
PAYSTACK_SECRET_KEY=<paystack-secret-key>
PAYSTACK_WEBHOOK_SECRET=<whsec-signing-secret>   # blank: legacy x-paystack-signature
```

and the Paystack webhook pointed at `/api/payments/paystack/webhook/`. A
transfer Paystack accepts stays `sending` until `transfer.success`,
`transfer.failed` or `transfer.reversed` arrives for that attempt's reference
(`party-<id>-<attempt>` or `pay-<id>-<attempt>`).

## The models

```
County -> Constituency -> Ward -> RegistrationCentre

User (candidate | campaign manager | mobilizer)
  ├── AuthToken       the live sign-in
  ├── CampaignMember  the one campaign it is on
  └── Campaign  -> Target      vote goal per ward or centre
                -> Mobilizer   organizer on a ward
                -> Event       meeting or rally
                -> Supporter   someone who signed up
```

`office_level` picks which of `county`, `constituency` or `ward` a campaign
contests, and whether it organizes by ward or by registration centre. `Target`
holds the win number: half the projected votes cast, plus one, in `Decimal`.

UUID primary keys are set in Python. Enums are text with a CHECK constraint.
Deletes cascade in the database. An unloaded relationship raises an error naming
the `selectinload` to add. Passwords are Argon2id. `/docs` and `/openapi.json`
are served only when `DEBUG` is on.

## Migrations

One revision, `alembic/versions/…-schema_20261024.py`, builds the schema. After the
revisions are folded into one again, a database built from the old chain is
relabelled or rebuilt as `DEPLOY.md` describes.

```bash
uv run alembic revision --autogenerate -m "what changed"
uv run alembic upgrade head
uv run alembic upgrade head --sql        # print the SQL
```

`tests/test_migrations.py` fails when the models and the migrations disagree.

## Configuration

Read from the environment and `.env`; see `.env.example`. `SECRET_KEY` is
required and at least 32 characters.

## Known gaps

- Coordinator, Comms and Agent have permissions but no screens yet (PD-10);
  `createuser` offers only candidate, manager and mobilizer. An agent's "own"
  rows (events, payments) are empty until assignments exist (PD-37). The
  team API refuses an area for anyone but a coordinator; the database does
  not. Coordinators and comms officers are removed by an admin, not from the
  Team page. Downgrading `campaign_roles` turns a pending login into a plain
  inactive one.
- The map holds only the actions a route serves today; `team.approve`,
  `agents.*`, `team.id_read`, `assignments.write`, `sms.*`, `sharing.write`,
  `site.write` and `export` arrive with their routes. Payment release stays
  with the Manager until approval routing (PD-37).
- Two rows differ from section 0.2 by decision: a Mobilizer reads targets
  and sends event invites in their own ward. `mobilizers.read` is not a row
  there; it keeps who reads the mobilizer list as before, plus coordinators
  in their area. A coordinator cannot set a mobilizer to no ward, as a place
  with no ward is outside every area.
- A coordinator sees payments through their events' places, so a payment
  with no event never shows to them. `area_ids` reads the caller's areas
  without naming the campaign; one campaign per login keeps that exact.
- The party workspace: the member register lists members of every status; the
  dashboard's seat filter does not narrow its totals or the recruitment counts;
  a member who reapplies takes the recruiter of the new application, or none;
  the admin console builds the workspace's ~1,450 ward rows on each list.
- The website editor lists every approved aspirant but saves a candidate
  page only for one with a workspace; it does not mark the others. Saving a
  page for an aspirant whose campaign already holds a page with no aspirant
  fails at the database (500), and a page keeps its campaign if the
  aspirant's link ever changes; neither happens through today's flows.
- `tests/test_boundaries.py` reads import statements only: a star import,
  `importlib`, or reaching party code through a package attribute
  (`models.party.X`) is not caught, and a new campaign module must be added
  to its `CAMPAIGN` list by hand.
- The `InstallationType` middleware matches the raw request path, so serving
  the API under a path prefix (`root_path`) hides party routes in a party
  installation too.
- Code that prints a campaign's seat (`api/routers/campaigns.py`,
  `api/routers/targets.py`, `services/admin.py`) assumes one is set. A party
  workspace has none; PD-7 creates the first.
