# The demo installs

Three installations, each one Neon database and one Vercel project serving the site and `/api`
from one address. They are for showing the product for a few minutes at a time; nothing real
goes in them.

| Install | Address | Vercel project | Neon database | What it is |
| --- | --- | --- | --- | --- |
| Party demo | https://pamoja-demo-vert.vercel.app | `pamoja-demo` | `demo_party` | Pamoja Party: website, party console, Jane for Roysambu's campaign |
| Aspirant demo | https://kasarani-demo.vercel.app | `kasarani-demo` | `demo_aspirant` | David Otieno for Kasarani: candidate page and campaign |
| Blank | https://setup-demo.vercel.app | `setup-demo` | `demo_blank` | Empty, for trying `/setup` from scratch |

The databases are in Neon project `mzigo_crm` (`patient-flower-76867840`), branch `production`.
Their connection strings are in `backend/.env` as `NEON_PARTY`, `NEON_ASPIRANT` and `NEON_BLANK`.

## Demo choices and what production uses instead

| Area | Demo | Production |
| --- | --- | --- |
| Hosting | Vercel: the frontend and the API as Vercel Services in one project | A long-running server (the `Dockerfile`, on Fly or any container host) |
| Party inbox (join, leave, stop volunteering) | `PARTY_INBOX_SECONDS=0`: no background loop; requests are applied when a party officer opens a console page | `PARTY_INBOX_SECONDS=60`: the loop applies them every minute, so nothing waits for an officer |
| Payments reconciliation | `RECONCILE_HOURS=0` (practice mode has nothing to reconcile) | `RECONCILE_HOURS=24` with Paystack live |
| Uploads | Not used: seeded content uses image links, and Vercel keeps no files | `UPLOAD_DIR` on a disk that persists and is backed up |
| Paystack, SMS, email | Practice mode | Live keys in the environment |
| Passwords | One easy password per install for every login | Each person's own password, set through their invite link |
| Rate limits | In memory, per Vercel instance, so looser | In memory on one server |

## Logins

Every login on an install shares one easy password, kept out of the repository and handed over
with the demo. Emails are `<name>@demo.pamoja.test`.

| Party demo | Aspirant demo |
| --- | --- |
| `admin` (party super admin) | `admin` (site admin) |
| `membership`, `nominations`, `comms` (party offices) | `candidate` (David Otieno) |
| `aspirant` (Jane Wanjiru), `manager`, `mobilizer` | `manager`, `mobilizer` |
| `volunteer` (member account) | |

## Rebuilding a demo database

From `backend/`, with the database's string in `DATABASE_URL`:

```bash
export DATABASE_URL=$(grep '^NEON_PARTY=' .env | cut -d= -f2-)
uv run alembic upgrade head
uv run campaign-crm seed
uv run campaign-crm demo-install party --password <12+ characters>
for u in admin membership nominations comms aspirant manager mobilizer volunteer; do
  uv run campaign-crm reset-password -u $u --password <the demo password>
done
```

The aspirant demo is the same with `NEON_ASPIRANT`, `demo-install aspirant`, the logins
`admin candidate manager mobilizer` and its own password.

`demo-install` refuses a database that is already set up. To start again, empty it first:
`uv run campaign-crm reset-database --yes <database name>`, then the commands above.

## The blank install

`demo_blank` is migrated and seeded with the reference data only. To let someone try setup, print
a token (valid 24 hours, spent on use) and give it to them with the site's `/setup` address:

```bash
export DATABASE_URL=$(grep '^NEON_BLANK=' .env | cut -d= -f2-)
uv run campaign-crm setup-token
```

To offer setup again afterwards, empty it with `reset-database`, then `alembic upgrade head` and
`campaign-crm seed`.

## Vercel projects

`vercel.json` at the repository root defines two services: `web` (the Vite app in `frontend/`,
deep paths fall back to `index.html`) and `api` (the FastAPI app, loaded from `backend/asgi.py`).
`/api/*` and `/health` go to `api`; everything else to `web`. `frontend/.env.production` builds
the app against `/api` on the same address.

`.vercelignore` uploads only `vercel.json`, `frontend/` and `backend/`, without `.env` files,
the virtualenv, uploads or tests.

`tools/deploy-demo.sh <project> <NEON_PARTY|NEON_ASPIRANT|NEON_BLANK>` creates the project if
needed, links it, sets the variables below from `backend/.env` and deploys to production. It
needs the Vercel CLI signed in (`npx vercel login`). Each install is its own Vercel project with
these environment variables (Production):

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | that install's Neon connection string |
| `SECRET_KEY` | 48 random characters, different per project |
| `PARTY_INBOX_SECONDS` | `0` |
| `RECONCILE_HOURS` | `0` |
| `CORS_ALLOW_ORIGINS` | `[]` |
| `PUBLIC_URL` | the project's address |
| `DEBUG` | `false` |

## Known gaps

- Vercel functions and the Neon database both sleep when idle; the first request after a quiet
  spell waits a few seconds.
- Vercel's Hobby plan is for non-commercial use; a demo shown to buyers belongs on Pro.
- An upload on these sites (logo, photo, document) is not kept.
