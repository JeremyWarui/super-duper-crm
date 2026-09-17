# Campaign CRM - backend

FastAPI, SQLAlchemy 2.0 (async) and Pydantic v2, on Postgres or CockroachDB. Managed with `uv`.

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
```

The admin commands run the same service as the admin console. A refusal prints
its reason and exits 1.

`seed` loads the IEBC 2022 register from `data/`: 47 counties, 290
constituencies, 1450 wards and 27,273 registration centres, with each county's
turnout. Ward names from the gazetted register and the centres file are matched
after folding punctuation, and a clipped name matches when only one ward fits.
Diaspora (48) and prison (49) rows are skipped.

`demo` builds the Roysambu MP campaign with mobilizers, events and supporters on
some wards, and prints five logins, generated per run unless `--password` or
`DEFAULT_USER_PASSWORD` is set:

```
  aspirant     Candidate: the cockpit, adds mobilizers
  manager      Campaign manager: the full war room
  mobilizer    Mobilizer: one ward
  newaspirant  Candidate with no campaign: starts at setup
  newmanager   Manager with no campaign: starts at setup, and is asked for the aspirant
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
| `POST /api/auth/register/` | Sign up as a candidate or a manager, signed in. Open. |
| `POST /api/auth/login/` `…/logout/` | Username and password for a token; sign out. |
| `GET /api/counties/` `…/{id}/`, `/api/constituencies/`, `/api/wards/`, `/api/centres/` | Reference geography; a mobilizer sees one ward. |
| `GET /api/campaigns/` `…/{id}/` | The caller's campaign. |
| `POST /api/campaigns/setup/` | Create a campaign, its candidate, and all its targets. |
| `POST /api/campaigns/{id}/generate_targets/` | Rebuild the targets after new data. |
| `GET POST /api/targets/`, `PATCH DELETE …/{id}/` | The win number per unit. |
| `GET POST /api/mobilizers/`, `DELETE …/{id}/` | Who works which ward. |
| `GET POST /api/events/`, `DELETE …/{id}/`, `POST …/{id}/record/`, `…/{id}/invite/` | Events, attendance, SMS invitations. |
| `GET POST /api/supporters/`, `DELETE …/{id}/` | The supporter register. |
| `GET /api/strategy/?campaign=` | The computed dashboard. |
| `POST /api/users/`, `DELETE …/{id}/` | Mobilizer logins; the password is returned once. |
| `/api/admin/…` | The console; superusers only. |

A foreign key travels under the bare name (`ward`, not `ward_id`), and reads
carry the parent's name beside it. Every error is `{"detail": "<sentence>"}`.

## Rules

- **One campaign per login.** Every route that puts a login on a campaign
  refuses a second one, and a unique index on `campaign_members.user_id` refuses
  it in the database.
- **A campaign belongs to its candidate**, the member whose role is candidate; a
  partial unique index allows one. A candidate sets up their own campaign; a
  manager sets one up by creating the aspirant's login. Whoever sets it up must
  be on no campaign.
- **Inside a campaign only mobilizers are added or removed**, by its manager or
  its candidate. A manager signs up, or an admin puts one on.
- **Only an admin deletes a campaign**, and that deletes everything on it and the
  logins of its people.
- **Scoping is by membership.** A campaign the caller is not on answers 404; a
  mobilizer reads and writes only their own ward.

| | Candidate | Manager | Mobilizer |
|---|---|---|---|
| Read the campaign and its strategy | yes | yes | their ward |
| Read the supporter register | no | yes | their ward |
| Set a campaign up | yes | yes | no |
| Add or remove mobilizers | yes | yes | no |
| Change targets | no | yes | no |
| Schedule and record events | no | yes | their ward |
| Register supporters | no | yes | their ward |
| Delete a campaign, reach `/api/admin/` | no | no | no |

## The admin console

A superuser (`createuser --superuser`) gets `/api/admin/`: every campaign with
its team, wards and size; every login and its campaign; rename and delete a
campaign; add and remove members; create a login; reset a password; disable or
enable a login. An admin cannot disable themselves or the last active superuser,
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

One revision, `alembic/versions/…_0001_schema.py`, builds the schema.

```bash
uv run alembic revision --autogenerate -m "what changed"
uv run alembic upgrade head
uv run alembic upgrade head --sql        # print the SQL
```

`tests/test_migrations.py` fails when the models and the migrations disagree.

## Configuration

Read from the environment and `.env`; see `.env.example`. `SECRET_KEY` is
required and at least 32 characters.
