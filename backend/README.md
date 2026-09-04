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
uv run uvicorn backend.main:app --reload  # http://127.0.0.1:8000/docs
```

Checks:

```bash
uv run pytest        # 386 tests, ~3 min, no database server needed
uv run ruff check .
uv run ruff format .
```

## Command line

```bash
uv run campaign-crm seed          # counties, constituencies, wards, turnout; --force to reload
uv run campaign-crm demo          # one campaign, one account per role
uv run campaign-crm createuser -u amina -r manager
```

`seed` reads the CSVs in `data/` and loads the whole 2022 register: 47 counties,
290 constituencies, 1450 wards and 27,273 registration centres, with each
county's turnout.

Centres come from the IEBC's per-polling-station PDF rather than the KNBS files,
and the two sources spell some wards differently, so the import folds the
punctuation they disagree about (`Ng’ombe` against `NG'OMBE`, `Njabini/Kiburu`
against `NJABINI\KIBURU`) and matches a name the PDF clipped to its column width
when exactly one ward could have been meant. Rows in counties 48 and 49 are the
diaspora and prisons, which sit in no ward, and are left out rather than counted
as failures. Every remaining row lands: a ward's centres add up to the register
that KNBS reports for it, which is the check that the join is right.

`demo` builds the Roysambu MP campaign - 5 wards, win number 43,050 - with
mobilizers, events and supporters on some wards and not others, so the strategy
read has real gaps to point at. It creates three accounts, `aspirant` (candidate),
`manager` and `mobilizer`, and prints their passwords:

```
Sign in at http://localhost:5173 as (shown once, re-run to reset):
  aspirant   Kx8fQ2mNpR4w   Candidate: read-only cockpit
  manager    7bTzY9vLwE3k   Campaign manager: the full war room
  mobilizer  Qn5jH8sVdA2c   Mobilizer: Githurai only
```

Each password is generated per run, so nothing that looks like a credential is
committed and a clone of this repo hands out no working logins. Re-running the
command resets them. To pin them instead:

```bash
uv run campaign-crm demo --password whatever-you-like
```

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
│   │   ├── scope.py       which campaigns and wards a caller may touch
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
| `POST /api/campaigns/setup/` | Create a campaign and all of its targets in one call. |
| `POST /api/campaigns/{id}/generate_targets/` | Rebuild them after loading new data. |
| `GET POST /api/targets/`, `PATCH DELETE …/{id}/` | The win number per unit. |
| `GET POST /api/mobilizers/`, `DELETE …/{id}/` | Who is working which ward. |
| `GET POST /api/events/`, `DELETE …/{id}/` | Rallies and meetings. |
| `POST /api/events/{id}/record/` | Close an event with its attendance. |
| `POST /api/events/{id}/invite/` | Text the event's supporters, and set how many were reached. |
| `GET POST /api/supporters/`, `DELETE …/{id}/` | The register. **POST is open**, so a field form works signed out. |
| `GET /api/strategy/?campaign=` | The computed dashboard. |

A foreign key travels under the related model's bare name - `ward`, not
`ward_id` - and reads carry the parent's name alongside it, so a list is
readable without a second request.

## Who may do what

Enforced per route, not in the UI.

| | Candidate | Manager | Mobilizer |
|---|---|---|---|
| Read the campaign and its strategy | yes | yes | their ward only |
| Read the supporter register | no | yes | their ward only |
| Set a campaign up | yes | yes | no |
| Change targets, mobilizers | no | yes | no |
| Schedule and record events | no | yes | their ward only |
| Register supporters | no | yes | their ward only |

A campaign the caller has no route into answers 404, not 403, so an outsider
cannot probe for one. A mobilizer with no profile row sees nothing rather than
everything.

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
AT_API_KEY=your-key
AT_SENDER_ID=                 # blank uses the shared short code
```

The app refuses to start if the gateway is selected without credentials, rather
than failing on the first invitation nobody receives. `services/sms.py` holds
the provider interface; everything above it is written against that and does not
know which one is in use.

## The models

```
County -> Constituency -> Ward -> RegistrationCentre
                               -> PollingStation

User (candidate | campaign manager | mobilizer)
  ├── AuthToken   the live sign-in, deleted on sign-out
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
  constituencies and wards; deleting a mobilizer's login keeps the mobilizer.
- **Money-shaped maths uses `Decimal`**, not float. Float rounding at the halfway
  point moves a win number by a whole vote.
- **Relationships are not loaded lazily.** Reading one that was not fetched
  raises an error naming the `selectinload` you need, rather than firing a
  hidden query.
- **Passwords are Argon2id**, and are rehashed on sign-in when the parameters
  have moved on.

## Known gaps

1. `PollingStation.centre_code` and `centre_name` are free text that repeat
   `RegistrationCentre`. They should be a foreign key.
2. `Campaign` has three geography columns and only one applies. `POST /setup/`
   fills in the right one, but nothing in the schema stops a ward campaign from
   also setting `county_id`.
3. `Mobilizer` has no uniqueness rule, so a ward can hold any number of them.
4. Nothing ties a **manager** to a campaign, so a manager sees every campaign on
   the system. Fixing it means a membership table.
5. `POST /api/supporters/` is open by design, for field self-registration. That
   also makes it the one route an anonymous caller can write through.
6. Polling stations are still empty. Targets are centre-level, so nothing needs
   them yet; `PollingStation` exists for when election-day work does.
7. The Africa's Talking adapter has never run against the live gateway - there
   is no subscription. Its request shape and its parsing are covered against
   recorded replies; what is unproven is the network call itself.
8. Invitations are not recorded. The reply says what happened, and nothing
   stores it, so there is no history of what was sent to whom.

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

## Configuration

Read from the environment and from `.env`; see `.env.example`. `SECRET_KEY` has
no default and must be at least 32 characters.
