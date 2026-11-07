# Developer guide

For a developer taking over the code. It says where things are, how to run them, and how the
checks work. What the system does and why lives in the documents below; this guide does not
repeat them.

## What to read first

1. [`docs/SYSTEM.md`](../SYSTEM.md): what the code does today, its rules, roles and
   architecture.
2. [`docs/Product_Design.md`](../Product_Design.md): the product plan. **Section 0, "Revision
   R1", overrides every other section**, and the whole document overrides the older design
   documents where they disagree. Its section 0.2 is the permissions map the code follows.
3. The design documents, as reference for how the built parts work:
   - [`docs/Identity_Access_Design.md`](../Identity_Access_Design.md): logins, party offices,
     the member register
   - [`docs/Aspirants_Design.md`](../Aspirants_Design.md): nominations and nominee workspaces
   - [`docs/Subscriptions_Design.md`](../Subscriptions_Design.md): hosting and subscriptions,
     which Revision R1 took out of the product; read it only for history
   - [`docs/Website_Design.md`](../Website_Design.md): the public website
   - [`docs/Volunteers_Design.md`](../Volunteers_Design.md): volunteers and member accounts
   - [`docs/Design_Coverage.md`](../Design_Coverage.md): which mockup goes with which code and
     ticket; the mockups are in `docs/party-platform-design/party-platform-design/screens/`
4. [`backend/README.md`](../../backend/README.md): the API, the rules route by route, every
   outside service and its settings, and the known gaps.

## Layout

```
├── backend/      FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 + Alembic, managed with uv
│   ├── src/backend/
│   │   ├── main.py        the app
│   │   ├── config.py      settings from the environment and backend/.env
│   │   ├── cli.py         the campaign-crm command
│   │   ├── api/           deps.py (sign-in and guards), scope.py, install.py, routers/
│   │   ├── models/        the tables; enums.py holds every choice set
│   │   ├── schemas/       request and response shapes
│   │   ├── services/      the business rules and the outside-service adapters
│   │   └── seed/          the CSV loaders and the demo
│   ├── alembic/versions/  the migrations
│   ├── data/              the 2022 reference CSVs
│   ├── tests/             gate tests
│   └── evals/             the frontend contract and the walks across statuses
├── frontend/     React 19 + Vite, React Query, Zustand, Tailwind CSS v4 and the UI kit
├── contracts/    frontend-api.json: every field the SPA reads and sends
├── deploy/       the self-host package: docker-compose.yml, Caddy, nightly backup
├── tools/        secret-scan/, the scanner the pre-commit hook and CI run
├── ui-kit/       the design kit the screens are built from
└── docs/         the system brief, the design documents, and handover/
```

`Dockerfile` at the root builds the one app image (the built SPA plus the API) that
`deploy/docker-compose.yml` runs.

## Run it locally

Needs Python 3.13, `uv`, Node and npm, and a local Postgres. The commands are the ones in the
root `README.md` and `backend/README.md`.

Backend, in one terminal:

```bash
cd backend
uv sync --group dev
createdb campaign_crm
cp .env.example .env              # set SECRET_KEY (32+ characters) and DB_PASSWORD
uv run alembic upgrade head
uv run campaign-crm seed          # counties, constituencies, wards, registration centres
uv run uvicorn backend.main:app --port 8000
```

`backend/.env` names the database with `DB_NAME`, `DB_USER`, `DB_PASSWORD` and `DB_HOST` and
`DB_PORT`, or with one `DATABASE_URL`, which wins. For a server that restarts on a code
change, use `uv run watchfiles "uvicorn backend.main:app" src .env` instead; on Windows
`uvicorn --reload` keeps serving the old code.

A new database has no site settings, so every `/api` route but `/api/setup/*` answers 503
until the first-run setup is done. Either run the setup in the browser:

```bash
uv run campaign-crm setup-token   # one use, valid 24 hours; paste it at /setup
```

or seed the demo, which also prints its logins:

```bash
uv run campaign-crm demo
```

Frontend, in a second terminal:

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173, proxies /api to port 8000
```

`uv run campaign-crm --help` lists every command (seed, demo, createuser, setup-token,
backup, restore, export, the imports and the admin operations).

## The two organisation types

Every copy is one of two types, chosen once at setup and never changed
(`site_settings.organisation_type`, `OrganisationType` in `models/enums.py`):

- **party**: the public website, the party office (members, volunteers, branches,
  nominations, party texts) and the party's national coordination workspace, plus a hosted
  workspace for each approved aspirant;
- **aspirant**: the aspirant's own website and one standalone campaign workspace.

Routes that exist in one type only are declared with a route class from `api/install.py`:
`PartyOnlyRoute` or `AspirantOnlyRoute`. In the other type they answer 404, exactly as an
unknown path does. A router that mixes both kinds of route puts the party ones on a
`party_router`.

Campaign code never imports party code. `tests/test_boundaries.py` reads the imports of every
module in its `CAMPAIGN` list and fails on one that reaches the `PARTY` modules; a new
campaign module must be added to that list by hand.

## Tests, evals and lint

### Backend, SQLite lane (the default)

```bash
cd backend
uv run pytest                     # tests/ and evals/, on in-memory SQLite
uv run pytest tests               # tests only
uv run pytest evals               # evals only
```

No database server and no network. `tests/conftest.py` sets `DATABASE_URL` to in-memory
SQLite for the run, so no test can reach a real database whatever `.env` says.

**Both organisation types.** Every test that uses the `client` fixture runs twice, once as a
party and once as an aspirant installation: `[party]` and `[aspirant]` in its id. A test or
module marked `party_only` (`pytestmark = pytest.mark.party_only`, registered in
`pyproject.toml`) runs once, as a party. A test that parametrizes `organisation_type` itself
keeps its own values.

### Backend, Postgres lane

```bash
cd backend
TEST_POSTGRES=1 uv run pytest
```

What it needs, from `tests/conftest.py`:

- a running local Postgres, named by the `DB_*` values in `backend/.env`;
- `DB_HOST` set to `localhost`, `127.0.0.1` or `::1`: any other host is refused, so the suite
  can never reach a deployed database;
- a `DB_USER` allowed to create and drop databases, since the lane connects to the `postgres`
  database to do so.

Each run creates `<DB_NAME>_pytest_<process id>`, builds it with the real migrations, empties
every table before each test, and drops it at the end, so two runs at once never share one.
Tests that only Postgres can prove (row locks, every migration down and up again) are skipped
on SQLite with "needs TEST_POSTGRES=1".

### Evals

`backend/evals/` holds the checks that measure the whole rather than one rule:

- `test_frontend_contract.py`: the API still offers every field the SPA reads and accepts
  every field it sends (below);
- `test_aspirant_access_walk.py`, `test_member_status_walk.py`: every aspirant and member
  status, walked across the routes it opens and closes;
- `test_inbox_constant_work.py`: the party's public join and withdraw queue does the same
  work whatever the register holds;
- `test_live_database.py`: skipped unless asked for. It checks TLS, the latest migration and
  the seeded geography on a real database:

  ```bash
  LIVE_DATABASE=1 uv run pytest evals/test_live_database.py -s
  ```

### Frontend

```bash
cd frontend
npx vitest run                    # the same as npm test
npx vitest run --maxWorkers=1     # on a machine with little memory
npm run build
npm run lint                      # oxlint
```

jsdom, no server needed. Vitest runs files in parallel workers; on a small machine one worker
keeps it from running out of memory.

### Lint

```bash
cd backend
uv run ruff check src tests evals
uv run ruff format --check src tests evals
```

```bash
cd frontend
npm run lint
```

Ruff's rules and the 100-character line are in `backend/pyproject.toml`; `alembic/versions` is
excluded. Oxlint reads `frontend/.oxlintrc.json`.

## Route guards

`tests/test_route_guards.py` walks every route the app mounts:

- every API route needs a login unless it is listed in `PUBLIC_ROUTES`; a new public route
  fails the suite until it is added there, and a removed one fails it as a stale entry;
- exactly the routes matching `PARTY_ONLY_PATHS` are party-only, and each answers 404 in an
  aspirant installation;
- the aspirant website routes are aspirant-only and missing in a party installation.

Inside a campaign, routers guard with `require("<action>")` from `api/deps.py`. The actions
and the roles that may do each, with their reach (`all`, `area`, `own`), are the `MAP` in
`services/permissions.py`; `api/scope.py` applies the reach to every read and write.
`tests/test_permissions.py` holds the map to section 0.2 of `docs/Product_Design.md`. A new
action goes into `MAP` and that test together.

## The frontend contract

`contracts/frontend-api.json` lists every route the SPA reads, the fields it reads from each,
the fields it sends, the enums it relies on and the routes that answer with no content. Both
sides check it:

- `backend/evals/test_frontend_contract.py` checks the backend's OpenAPI schema still offers
  and accepts every listed field;
- `frontend/tests/contract.test.js` checks the frontend's test fixtures carry every listed
  field, and reads the source (`frontend/tests/apiCalls.js`) to check it calls every route
  the contract lists and no route it leaves out.

Rename a field on one side and both suites fail until the other side and the contract follow.
Change the contract in the same commit as the code.

## Adding a migration

Revisions are one chain in `backend/alembic/versions/`, named
`YYYYMMDD_HHMM-<revision id>.py` with a readable revision id (`drop_two_step`, not a hash):

```bash
cd backend
uv run alembic revision --autogenerate --rev-id <name> -m "what changed"
```

Then rename the generated file to the `YYYYMMDD_HHMM-<name>.py` pattern, check that
`down_revision` names the previous head, and write the docstring as one line on what the
revision does. Autogenerate misses some things (CHECK constraints, partial index `WHERE`
clauses, data moves): read the file and finish it by hand. Use `op.batch_alter_table` for
column changes, so SQLite can apply them too.

Run both lanes before committing:

```bash
uv run pytest tests/test_migrations.py                    # SQLite
TEST_POSTGRES=1 uv run pytest tests/test_migrations.py    # Postgres
uv run alembic upgrade head --sql                         # print the SQL
```

`tests/test_migrations.py` fails when the migrated schema and the models disagree (tables,
columns, indexes, foreign keys), when the revisions do not form one chain, or, on Postgres,
when a revision does not downgrade and upgrade again. A revision that moves data gets its own
test there.

## Outside services

Every outside service sits behind a small adapter in `backend/src/backend/services/`, picked
by a setting in `.env`. Each runs in a practice mode until the keys are set, so the whole
system works and can be tested without sending anything or moving money. The settings are in
`backend/README.md` and `deploy/.env.example`; the console's Health tab shows which mode each
is in and offers a test.

| Adapter | Setting | Practice mode | Real provider |
|---|---|---|---|
| `services/email.py` | `EMAIL_PROVIDER` | `practice`: sends nothing, writes the email (link included) to the app's log; `email_log` keeps it with the link removed | `smtp`, any SMTP server (`SMTP_*`) |
| `services/sms.py` | `SMS_PROVIDER` | `console`: records the text, sends nothing | `africastalking` (`AT_USERNAME`, `AT_API_KEY` and `AT_SENDER_ID`) |
| `services/texting.py` | (uses `sms.py`) | every text goes through it: opt-outs dropped, one `sms_log` row per number (`practice` in practice mode) | delivery reports and STOP replies come back through it |
| `services/payouts.py` | `PAYOUT_PROVIDER` | `practice`: moves no money, marks each release paid under a `PRACTICE-` reference | `paystack`, M-Pesa transfers (`PAYSTACK_SECRET_KEY` and `PAYSTACK_WEBHOOK_SECRET`) |
| `services/oidc.py` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | off: the Google button is hidden and its routes answer 404 | Google sign-in (OpenID Connect with PKCE) |

`tests/fixtures/` holds the recorded provider replies the adapters are tested against.

## Commit hooks and CI

Turn the hook on once per clone:

```bash
git config core.hooksPath .githooks
```

`.githooks/pre-commit` is the only hook. It runs `tools/secret-scan/scan.py --staged` with
Python 3.10 or later and refuses the commit when a staged file carries a password, key or
token; it prints the path, line and rule, never the value. If no suitable Python is found the
commit is refused too. See `tools/secret-scan/README.md`; paths the scanner skips are
listed, one glob per line, in `tools/secret-scan/allow.txt`.

`.github/workflows/` runs on every push and pull request:

- `backend-tests.yml`: a matrix of `sqlite` and `postgres` (a `postgres:17` service
  container). Each job runs `uv sync --frozen`, ruff check and ruff format check on
  `src tests evals`, then `uv run pytest -q -p no:cacheprovider tests evals`; the Postgres job
  writes a `backend/.env` for the container and sets `TEST_POSTGRES=1`.
- `secret-scan.yml`: the scanner's own tests, a scan of every tracked file, and a scan of the
  lines every new commit in the push or pull request adds.

CI does not run the frontend tests, build or lint. Run them before pushing.

## Known gaps

The open gaps, area by area, are listed under `## Known gaps` at the end of
[`backend/README.md`](../../backend/README.md), with shorter `### Known gaps` lists under the
sections they belong to (setup, imports, personal data).
