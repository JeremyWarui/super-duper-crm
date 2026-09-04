# Campaign CRM

A Kenyan campaign management tool built around the **win number**: the votes a
candidate needs to take a seat, broken down to the unit their team actually
works - a ward for an MP or governor race, a registration centre for an MCA one.

FastAPI and SQLAlchemy on Postgres, React and Vite in the browser, on the real
GE2022 register.

## Run it

Two terminals. Backend first.

```bash
cd backend
uv sync --group dev
createdb campaign_crm
cp .env.example .env                      # set SECRET_KEY and your Postgres password
uv run alembic upgrade head
uv run campaign-crm seed                  # 47 counties, 290 constituencies, 1450 wards
uv run campaign-crm demo                  # the demo campaign and its three logins
uv run uvicorn backend.main:app --reload  # http://127.0.0.1:8000/docs
```

```bash
cd frontend
npm install
npm run dev                               # http://localhost:5173
```

## Seeing all three roles

Each role gets a different app, and the difference is enforced on the server, not
just hidden in the UI. `campaign-crm demo` seeds one account per role against the
same campaign, so you sign out and back in to switch.

| Sign in as | Password | What you get |
|---|---|---|
| `aspirant` | `demo-aspirant-2027` | **Candidate.** Overview, ward performance, events, strategy. Reads only. |
| `manager` | `demo-manager-2027` | **Campaign manager.** All of that plus targets, mobilizers and supporters, and every write. |
| `mobilizer` | `demo-mobilizer-2027` | **Mobilizer.** One ward. Record events, register supporters, nothing else. |

The demo builds the Roysambu MP seat: 5 wards, 153,772 registered voters, a win
number of 43,050. Some wards are staffed and worked and some are not, so the
strategy read has real gaps to point at.

## Structure

```
├── backend/     FastAPI + SQLAlchemy 2.0 + Pydantic v2, Postgres, uv
└── frontend/    React 19 + Vite, React Query, Zustand
```

Each has its own README, its own tests, and runs on its own.

## The idea

Everything hangs off one number. Give the app a seat and an area and it pulls in
every unit, sets each one's turnout to its county's 2022 figure, and works out
what half the projected votes plus one comes to. From there the team's job is
visible: which units carry the most of that number, which are behind, which have
nobody working them.

The strategy read is computed on every request from targets, events and
mobilizers. Nothing about it is stored, so what the screen says can never
disagree with the rows underneath it.

## Checks

```bash
cd backend  && uv run pytest && uv run ruff check .   # 272 tests
cd frontend && npm test && npm run build              # 77 tests
```

Neither suite needs a database server or the network.

## Data

`backend/data/` carries the processed GE2022 CSVs (counties, constituencies,
wards, registered voters, county results), from
[nyimbi/kenya_election_data_2022](https://github.com/nyimbi/kenya_election_data_2022).

Registration centres come from the IEBC's per-polling-station PDF, which is a
browser download - see `backend/README.md`. Without `data/centres.csv` a ward
(MCA) campaign has no centres to target, and setup says so rather than reporting
a win number of zero.
