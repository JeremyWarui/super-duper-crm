# Shabaha

A Kenyan campaign management tool for one candidate contesting one seat: MCA, MP, Women Rep,
Senator, Governor or President. It is built around the **seat target**: the votes the
candidate needs, broken down to the unit their team actually works, a ward for most seats and
a registration centre for an MCA one.

FastAPI and SQLAlchemy on Postgres, React and Vite in the browser, on the real GE2022
register and past results from 2013 to 2022.

What the system is for, its rules, scope and architecture:
[`docs/SYSTEM.md`](docs/SYSTEM.md).

## Run it

Two terminals. Backend first.

```bash
cd backend
uv sync --group dev
createdb campaign_crm
cp .env.example .env                      # set SECRET_KEY and your Postgres password
uv run alembic upgrade head
uv run campaign-crm seed                  # 47 counties, 290 constituencies, 1450 wards, 27,273 centres
uv run campaign-crm seed-results          # past results, 2013 to 2022, for the targets
uv run campaign-crm setup-token           # the one-time token for /setup
uv run watchfiles "uvicorn backend.main:app" src .env   # http://127.0.0.1:8000/docs
```

```bash
cd frontend
npm install
npm run dev                               # http://localhost:5173
```

Open http://localhost:5173: every page goes to `/setup` until it is done. Paste the token
and go through the six steps: name and colours, contacts, the first superuser, the campaign
(seat, area, election date and the candidate's login), a preview of the seat target, and
check and finish. Sign-in links go to the server console while email is in practice mode.

Before the first commit, turn on the hook that refuses passwords, keys and
tokens (see `tools/secret-scan/README.md`):

```bash
git config core.hooksPath .githooks
```

## Seeing the roles

Each role gets a different app, and the difference is enforced on the server, not
just hidden in the UI. `campaign-crm demo` seeds one account per role against the
same campaign, so you sign out and back in to switch.

| Sign in as | What you get |
|---|---|
| `aspirant` | **Candidate.** Overview, ward performance, events, mobilizers, team, strategy. Adds or replaces the one manager, adds and assigns mobilizers, approves texts and payments. |
| `manager` | **Campaign manager.** Targets, mobilizers, team and contacts, texts and calls, and every write. Adds mobilizers and shares the sign-up links supporters use. |
| `mobilizer` | **Mobilizer.** One ward. Record events, add contacts, nothing else. |

The demo makes no superuser; the first one comes from `/setup`.

`campaign-crm demo` prints every password; they are generated per run, so
nothing credential-shaped is committed. `--password <value>` pins them.

The demo builds the Roysambu MP seat: 5 wards and 153,772 registered voters. Some wards are
staffed and worked and some are not, so the strategy read has real gaps to point at.

Other demo commands:

```bash
uv run campaign-crm demo-install --password <12+ characters>   # an empty database as the hosted demo
uv run campaign-crm demo-comms --phone <a> --phone <b>         # two consenting contacts and two drafts
uv run campaign-crm sms-worker                                 # send bulk-text batches as they fall due
uv run campaign-crm make-vapid-keys                            # a key pair for call alerts
```

The hosted demos and the texts-and-calls demo script are in [`docs/Demo.md`](docs/Demo.md).

## Structure

```
├── backend/     FastAPI + SQLAlchemy 2.0 + Pydantic v2, Postgres, uv
├── frontend/    React 19 + Vite, React Query, Zustand
├── contracts/   what the two agree on, checked from both sides
└── docs/        the system brief, the demo installs, and the handover guides
```

Each service has its own README, its own tests, and runs on its own.

`contracts/frontend-api.json` lists every field the SPA reads and sends.
`backend/evals/test_frontend_contract.py` checks the API still offers them;
`frontend/tests/contract.test.js` checks the SPA's fixtures and source still
match. Rename a field on one side and both fail until the other catches up.

## Handover

Each copy is installed and run by the buyer. What they need is in two places:

- [`deploy/`](deploy/README.md): the self-host package, one Docker Compose file with the
  database, the app, HTTPS and nightly backups.
- [`docs/handover/`](docs/handover/): the guides for running and changing a copy:
  `IT_Operations.md`, `Admin_Guide.md`, `User_Guides/`, `Developer_Guide.md`,
  `Handover_Checklist.md` (what the buyer receives and signs for), and `samples/`.

## The idea

Everything hangs off one number. Give the app a seat and an area and it pulls in every unit,
looks at the share of the vote the last winner of that seat took, and applies it to the votes
expected this time. That is the seat target. Each ward (or centre) is asked for its share of
it, by where the votes were cast. From there the team's job is visible: which units carry the
most of that number, which are behind, which have nobody working them.

The strategy read is computed on every request from targets, events and
mobilizers. Nothing about it is stored, so what the screen says can never
disagree with the rows underneath it.

The team reaches its people through texts and calls. Texts go through a compliance queue:
each one names the candidate, is in English or Kiswahili, goes only to contacts whose consent
covers it, and is sent in batches between 08:00 and 18:00 Nairobi time. Calls are audio or
video, joined at `/meet/<id>`, with an alert on the phones that turned alerts on.

## Checks

```bash
cd backend  && uv run pytest && uv run ruff check .
cd frontend && npm test && npm run build
```

Neither suite needs a database server or the network. One check does, and is
skipped unless asked for: it connects to the database in `backend/.env` and
confirms TLS, the latest migration and the seeded geography.

```bash
cd backend && LIVE_DATABASE=1 uv run pytest evals/test_live_database.py -s
```

## Data

`backend/data/` carries the processed GE2022 CSVs (counties, constituencies,
wards, registered voters, county results), from
[nyimbi/kenya_election_data_2022](https://github.com/nyimbi/kenya_election_data_2022).

`backend/data/history/` carries the past results for 2013, 2017 and 2022 the targets are
worked out from, from [Kura254's open data](https://www.kura254.com/open-data); its
`SOURCE.md` says what the file covers.

`data/centres.csv` holds 27,396 registration centres extracted from the IEBC's
per-polling-station PDF. A ward's centres add up to the register KNBS reports for
that ward, which is how the two independent sources check each other.

Polling stations are not loaded. Targets are centre-level, so nothing needs them
until election-day work does.
