# Campaign CRM - backend

FastAPI, SQLAlchemy 2.0 (async) and Pydantic v2, on Postgres. Managed with `uv`.

## Quick start

Needs a local Postgres running.

```bash
cd backend
uv sync --group dev
createdb campaign_crm                     # or: psql -c "CREATE DATABASE campaign_crm"
cp .env.example .env                      # fill in SECRET_KEY and your Postgres password
uv run alembic upgrade head               # create the tables
uv run campaign-crm seed                  # load the 2022 geography
uv run campaign-crm demo                  # build the demo campaign and its three logins
uv run watchfiles "uvicorn backend.main:app" src .env   # http://127.0.0.1:8000/docs
```

### Why not `uvicorn --reload`

On Windows its reloader restarts the worker with
`os.kill(pid, signal.CTRL_C_EVENT)`. That routes through
`GenerateConsoleCtrlEvent`, which wants a console process group id, and the
worker is a `multiprocessing` child that is not a group leader. The event lands
nowhere, `process.join()` blocks, and the server prints `Reloading...` and then
keeps serving the old code with no error. Reproduced on uvicorn 0.52.4 with a
three-line ASGI app, so it is the reloader rather than anything here.

`watchfiles` restarts the child by terminating it, which works. Watching `.env`
alongside `src` is what `--reload` does not do at all: settings are read once
per process, so a changed password or DSN needs the restart either way.

Checks:

```bash
uv run pytest        # 644 tests, ~3 min, no database server needed
uv run ruff check .
uv run ruff format .
```

## Command line

```bash
uv run campaign-crm seed          # counties, constituencies, wards, turnout; --force to reload
uv run campaign-crm demo          # one campaign, one account per role
uv run campaign-crm createuser -u root -r manager --superuser
uv run campaign-crm campaigns                    # who runs what
uv run campaign-crm campaign -c <campaign id>    # one campaign and its team
uv run campaign-crm users -r candidate           # logins, and what they reach
uv run campaign-crm assign-manager -u amina -c <campaign id>
uv run campaign-crm add-member -u juma -c <campaign id>
uv run campaign-crm remove-member -u juma -c <campaign id>
uv run campaign-crm reset-password -u jane
uv run campaign-crm deactivate -u jane           # and activate
```

`add-member` is the way back for anyone the console took off, whatever their
role; `assign-manager` is the manager-only shorthand that also carries `--only`.
Neither asks what capacity to give: a member holds the role their login already
has, because that is the column every permission check reads.

`seed` reads the CSVs in `data/` and loads the whole 2022 register: 47 counties,
290 constituencies, 1450 wards and 27,273 registration centres, with each
county's turnout.

Both sides are IEBC 2022 files, but different ones: wards and their voters come
from the gazetted register (`ke_ge22_01_grv_caw_v100.csv`), centres from the
per-polling-station PDF. The two spell some wards differently, so the import
folds the punctuation they disagree about (`Ng’ombe` against `NG'OMBE`,
`Njabini/Kiburu` against `NJABINI\KIBURU`) and matches a name the PDF clipped to
its column width when exactly one ward could have been meant. Rows in counties 48
and 49 are the diaspora and prisons, which sit in no ward, and are left out
rather than counted as failures. Every remaining row lands: a ward's centres add
up to its gazetted register, which is the check that the join is right. Two
Kimilili wards are the exception, and the source disagrees with itself there: 87
voters sit in Kibingei in the PDF and in Kimilili in the gazette.

`demo` builds the Roysambu MP campaign - 5 wards, win number 43,050 - with
mobilizers, events and supporters on some wards and not others, so the strategy
read has real gaps to point at. It creates five accounts and prints their
passwords. `aspirant`, `manager` and `mobilizer` are on the campaign;
`newaspirant` and `newmanager` are on nothing, so the setup flow is reachable:

```
Sign in at http://localhost:5173 as (shown once, re-run to reset):
  aspirant     <generated>    Candidate: the cockpit, adds mobilizers
  manager      <generated>    Campaign manager: the full war room
  mobilizer    <generated>    Mobilizer: Githurai only
  newaspirant  <generated>    Candidate with no campaign: starts at setup
  newmanager   <generated>    Manager with no campaign: starts at setup, and is
                              asked for the aspirant
```

Each password is generated per run, so nothing that looks like a credential is
committed and a clone of this repo hands out no working logins. Re-running the
command resets them. To pin them instead:

```bash
uv run campaign-crm demo --password <shared-password>
```

### One password for the whole demo

`DEFAULT_USER_PASSWORD` in `.env` is handed to every account the app creates,
not only the four the demo builds: the team members added through
`POST /api/users/`, and an aspirant created inline by `POST /api/campaigns/setup/`.
A demo then has one credential somebody can be told over the phone.

```bash
DEFAULT_USER_PASSWORD=<shared-password>
```

`demo --password` still wins over it. Blank, which is the default and what
`.env.example` ships, generates one password per account. **Leave it blank
anywhere real**: one shared password means whoever knows it can sign in as
every account created since it was set. The test suite forces it blank, so the
generated path is the one under test.

## Layout

```
backend/
├── alembic/               migrations
├── data/                  the 2022 reference CSVs
├── src/backend/
│   ├── main.py            the app and its middleware
│   ├── config.py          settings, read from the environment
│   ├── security.py        password hashing and token keys
│   ├── cli.py             seed, demo, createuser
│   ├── api/
│   │   ├── deps.py        the session, the caller, and what their role may do
│   │   ├── errors.py      one readable "detail" sentence per error
│   │   ├── scope.py       which campaigns, people and wards a caller may touch
│   │   └── routers/       one module per resource
│   ├── db/                declarative base, engine, session
│   ├── models/            the tables
│   ├── schemas/           request and response shapes
│   ├── seed/              the CSV loaders and the demo
│   └── services/          the win number, the strategy read, and sending SMS
├── tests/
└── evals/                 guards the schema, and the contract with the SPA
```

## The API

Everything lives under `/api`, with a trailing slash, and needs a
`Authorization: Token <key>` header unless noted.

| Route | What it does |
|---|---|
| `POST /api/auth/login/` | Username and password in, token and role out. Open. |
| `POST /api/auth/logout/` | Deletes the caller's token. |
| `GET /api/counties/` `…/{id}/` | Reference geography. |
| `GET /api/constituencies/?county=` | Filtered for the onboarding pickers. |
| `GET /api/wards/?constituency=` | A mobilizer sees only their own ward. |
| `GET /api/centres/?ward=` | Same. |
| `GET /api/campaigns/` `…/{id}/` | The caller's campaigns. |
| `POST /api/campaigns/setup/` | Create a campaign and all of its targets in one call. Names the candidate. |
| `POST /api/campaigns/{id}/generate_targets/` | Rebuild them after loading new data. |
| `GET POST /api/targets/`, `PATCH DELETE …/{id}/` | The win number per unit. |
| `GET POST /api/mobilizers/`, `DELETE …/{id}/` | Who is working which ward. |
| `GET POST /api/events/`, `DELETE …/{id}/` | Rallies and meetings. |
| `POST /api/events/{id}/record/` | Close an event with its attendance. |
| `POST /api/events/{id}/invite/` | Text the event's supporters, and set how many were reached. |
| `GET POST /api/supporters/`, `DELETE …/{id}/` | The register, for the campaign the caller is on. |
| `GET /api/strategy/?campaign=` | The computed dashboard. |
| `GET POST /api/users/`, `DELETE …/{id}/` | Logins for the team. The password is generated and returned once. |

A foreign key travels under the related model's bare name - `ward`, not
`ward_id` - and reads carry the parent's name alongside it, so a list is
readable without a second request.

## The admin console

Everything in the API is scoped to the caller's memberships, so no campaign role
can see past its own campaign. Running the deployment needs something that can,
and that is the `is_superuser` flag: a flag rather than a fourth role, so it
cannot be confused with the three campaign roles and cannot be signed up for.
`POST /api/auth/register/` rejects the field outright.

```bash
uv run campaign-crm createuser -u root -r manager --superuser
```

A superuser signing in gets `/api/admin/`, and the browser gives them the
console rather than a campaign. The routes are `overview`, `campaigns`,
`campaigns/{id}`, `users`, `users/{id}/reset-password`, `users/{id}/active`,
and adding or removing a member of a campaign. They live in
`api/routers/admin.py` over `services/admin.py`, and touch nothing in
`api/scope.py`, so widening what an admin reads cannot widen what a manager
reads.

`POST /api/admin/users/` creates a login of any role and returns its password
once. Naming a campaign puts them on it as it is made; a mobilizer must also be
given one of that campaign's wards, since the `Mobilizer` row is what scopes
them. A candidate cannot be added to a campaign that already has one: a
campaign's candidate is its member whose place is `candidate`, and a partial
unique index on `campaign_members` allows one.

The same operations are on the command line, through the same service, for when
the console cannot be reached:

```bash
uv run campaign-crm users -r candidate      # every login and where it reaches
uv run campaign-crm campaign -c <id>        # one campaign, its team and its size
uv run campaign-crm reset-password -u jane  # the only way back from a lost one
uv run campaign-crm add-member -u amina -c <id>
uv run campaign-crm remove-member -u amina -c <id>
uv run campaign-crm deactivate -u juma      # and activate
```

`reset-password` and `deactivate` both delete the account's token, so a live
session stops at once rather than at its next sign-in.

Three things the console will not do, because each ends with nobody able to run
the deployment:

- reset the operator's own password, which would sign them out before the new
  one reached the screen (`campaign-crm reset-password` does it instead);
- disable the last active superuser, though any other one can go, so a
  compromised account is still stoppable;
- put a superuser on a campaign, which would buy them nothing they cannot
  already read and would hide the campaign app from them.

A campaign manager cannot delete a superuser's login either, even when the
console has made one visible to them.

## Who may do what

Enforced per route, not in the UI.

| | Candidate | Manager | Mobilizer |
|---|---|---|---|
| Read the campaign and its strategy | yes | yes | their ward only |
| Read the supporter register | no | yes | their ward only |
| Set a campaign up | yes | yes | no |
| Add or remove a login | yes | yes | no |
| Change targets, mobilizers | no | yes | no |
| Reach `/api/admin/` | no | no | no |
| Schedule and record events | no | yes | their ward only |
| Register supporters | no | yes | their ward only |

Everyone is held to the campaigns they are a member of. `campaign_members` is
the only thing scoping reads, so it is one join for every role rather than a
branch per role. A campaign the caller has no route into answers 404, not 403,
so an outsider cannot probe for one, and a manager who has set nothing up sees
an empty list, which is what sends them to `POST /api/campaigns/setup/`.

## Sending invitations

`POST /api/events/{id}/invite/` texts an event's supporters and sets the event's
`number_reached`, which is what the attendance form later divides by. Sending it
is what fills that number in; before, somebody counted the register by hand.

```jsonc
{
  "message": "Town hall this Saturday, 2pm, Zimmerman social hall.",
  "support_levels": ["supporter", "undecided"],  // default: everyone
  "whole_campaign": false,                        // default: the event's ward
  "dry_run": false                                // work out the cost, send nothing
}
```

The reply says which numbers the gateway took, which it would not, which rows
had no usable number, and how many 160-character parts each message is billed at.

**Nothing is sent yet.** There is no Africa's Talking subscription, so the
default provider records the request, reports `delivered: false`, and says in
`detail` what to set to change that. `number_reached` only moves on a real
delivery, so the attendance rate is never divided by people nobody contacted.

Numbers are normalised to E.164 first. A register filled in by hand holds
`0712 345678`, `+254712345678` and `254-712-345-678` for one person; the gateway
would bill for three. Anything that cannot be read as a Kenyan number is
reported back rather than guessed at, because a wrong number is a message
delivered to a stranger.

To send for real:

```bash
SMS_PROVIDER=africastalking
AT_USERNAME=your-username     # or "sandbox" for their test gateway
AT_API_KEY=<africas-talking-api-key>
AT_SENDER_ID=                 # blank uses the shared short code
```

The app refuses to start if the gateway is selected without credentials, rather
than failing on the first invitation nobody receives. `services/sms.py` holds
the provider interface; everything above it is written against that and does not
know which one is in use.

## Whose campaign it is

A campaign belongs to its candidate, and `POST /api/campaigns/setup/` says so
explicitly rather than inferring it from whoever filled the form in.

- A **candidate** gets themselves. Naming anyone else is refused.
- A **manager** must name an aspirant with `candidate`, or create one inline
  with `new_candidate`. The reply carries that new login's password once. Only
  an aspirant the manager can already see may be named, so a second campaign for
  somebody they already set up reuses that login instead of colliding with the
  username.

Without this the manager becomes the campaign's candidate, and the aspirant
cannot see their own campaign.

## Adding the team

Inside a campaign, the only login anybody adds is a mobilizer's.

| Who | Adds |
|---|---|
| Campaign manager | The aspirant, named or created at `POST /api/campaigns/setup/`; mobilizers |
| Candidate | Mobilizers |
| Mobilizer | Nobody |

`POST /api/users/` accepts `role: "mobilizer"` and refuses anything else with a
400. `DELETE /api/users/{id}/` removes only a mobilizer's login; any other login
gets a 403, and an admin disables it from the console instead. `POST` and
`DELETE /api/mobilizers/` take a manager or the candidate, on their own campaign
only. A manager is never added from inside a campaign: they sign up for
themselves, or an operator puts one on with `campaign-crm assign-manager` or the
admin console. Membership rows are additive, so adding somebody never takes the
campaign off whoever is already on it.

A membership carries the role its login already has, and that role is never
passed in: `POST /api/admin/campaigns/{id}/members/` takes a user and nothing
else. Every permission check reads `users.role`, so a membership row saying
anything different would advertise a capacity its holder does not have - a
"mobilizer" who could delete the campaign.

A named mobilizer has to be on the campaign it is named for, on every route that
takes one: events, supporters and the mobilizer roster itself. `POST
/api/mobilizers/` will only attach a mobilizer login that is not already on the
ground, which is also what keeps `Mobilizer.user_id` unique.

`POST /api/users/` makes a login for a manager or a mobilizer. The password is
generated, returned once and never stored in the clear, so it cannot be fetched
again; the account has to be recreated if it is lost. A mobilizer also gets the
`Mobilizer` row that scopes them to a ward, and a manager is put on the campaign
they were added to; without either they sign in to an empty app. A campaign has
one candidate, whoever set it up, so this route will not make another.

Deleting a login leaves the mobilizer row behind, minus its `user_id`: the
person still worked that ward.

## The models

```
County -> Constituency -> Ward -> RegistrationCentre
                               -> PollingStation

User (candidate | campaign manager | mobilizer)
  ├── AuthToken       the live sign-in, deleted on sign-out
  ├── CampaignMember  a place on a campaign; what scopes every read
  └── Campaign  -> Target      vote goal per ward or centre
                -> Mobilizer   organizer on the ground
                -> Event       meeting or rally, with attendance
                -> Supporter   someone who signed up
```

A campaign contests one office. `office_level` decides which of `county`,
`constituency` or `ward` applies, and whether the campaign organizes by ward or
by registration centre.

`Target` holds the win number: half the projected votes cast, plus one. Call
`recompute_win_number()` after changing the projected turnout.

## How the models are set up

- **UUID primary keys**, generated in Python, so an object has its id before it
  is saved and ids are safe to show in URLs.
- **Enums are stored as text** with a CHECK constraint listing the valid values,
  so the database rejects a bad one.
- **Deletes are handled in the database.** Deleting a county removes its
  constituencies and wards; deleting a mobilizer's login keeps the mobilizer;
  deleting a member takes their membership row and leaves the campaign standing.
- **Money-shaped maths uses `Decimal`**, not float. Float rounding at the halfway
  point moves a win number by a whole vote.
- **Relationships are not loaded lazily.** Reading one that was not fetched
  raises an error naming the `selectinload` you need, rather than firing a
  hidden query.
- **Passwords are Argon2id**, and are rehashed on sign-in when the parameters
  have moved on.

## What a deployment does not hand out

`/docs`, `/redoc` and `/openapi.json` are served only when `DEBUG` is on. They
describe every route, field and schema, which is a map of the deployment to
anybody who asks for it; they are a development tool and a deploy leaves them
off. `app.openapi()` still builds the schema in the process, which is what the
contract checks read.

`ALLOW_REGISTRATION` is off unless a deployment sets it. A deploy that says
nothing does not take sign-ups from the internet; the admin console and the
invite routes work either way. `.env.example` turns it on, because local
development wants the sign-up flow reachable.

## Migrations

```bash
uv run alembic revision --autogenerate -m "what changed"
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head --sql        # print the SQL instead of running it
```

The connection string lives in `.env`, not in `alembic.ini`.

`tests/test_migrations.py` fails if you add a column and forget to generate a
migration for it.

Each revision runs in its own transaction (`transaction_per_migration`), so a
failure does not roll back the revisions before it.

### Upgrading to campaign_members

Two revisions. `b2c3d4e5f6a7` creates `campaign_members` and nothing else: it
alters no column and drops no table, so the DDL transaction stays pure for
CockroachDB. `c3d4e5f6a7b8` then fills it in, from `campaigns.candidate_id` and
from every `mobilizers.user_id` that is set. Running it twice adds nobody twice.

Managers are the exception, and cannot be backfilled: before this table there
was no column tying a manager to a campaign, which is the bug the table exists
to fix. So after upgrading, put them on by hand:

```bash
uv run campaign-crm campaigns                       # ids, candidates, managers
uv run campaign-crm assign-manager -u amina -c <campaign id>
```

`campaigns` marks a campaign with no manager `-- none --`. `assign-manager` adds
one beside whoever is already there; `--only` takes every other manager off.

### Dropping campaigns.candidate_id

Two more revisions make `campaign_members` the only record of who a campaign is
for. `d4e5f6a7b8c9` adds any missing candidate row, then stops the upgrade and
names every campaign that does not hold exactly one candidate row for the login
`campaigns.candidate_id` names. Fix those rows by hand and upgrade again.
`e5f6a7b8c9d0` drops the column and adds the index that allows one candidate per
campaign. Its downgrade puts the column back from the members.

## Configuration

Read from the environment and from `.env`; see `.env.example`. `SECRET_KEY` has
no default and must be at least 32 characters.
