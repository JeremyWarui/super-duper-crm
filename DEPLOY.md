# Deploying on Vercel, with Neon

Each installation is one Vercel project and one Neon Postgres database. `vercel.json` at the
repository root defines the project, in region `fra1` (Frankfurt):

| Service | Root | What it serves |
|---|---|---|
| `web` | `frontend/` | The built Vite app; any path without a file falls back to `index.html` |
| `api` | `backend/` | The FastAPI app, loaded from `backend/asgi.py` (`asgi:app`) |

`/api/*` and `/health` go to `api`, everything else to `web`, so the site and the API share one
address and need no CORS. `frontend/.env.production` builds the app against `/api` on that
address. `.vercelignore` uploads only `vercel.json`, `frontend/` and `backend/`, without `.env`
files, the virtualenv, uploads or tests.

The database is Neon Postgres in Frankfurt (`aws-eu-central-1`), next to the functions. Vercel
runs no migrations and no data loads: you run them from your machine against the Neon database,
as below.

The commands are bash. On Windows run them in Git Bash from the repository root;
`tools/deploy-demo.sh` calls the Vercel CLI through `npx.cmd`.

## Before the first deploy

Install Node.js (for `npx`) and `uv`, then sign in to Vercel and Neon. Both open a browser:

```bash
npx vercel@latest login
npx neon@latest login
```

`uv` supplies Python and the backend's dependencies, so nothing else is needed.

## 1. The database and its connection string

Create a database for the installation in your Neon project (console or CLI), then print its
connection string with certificate checking:

```bash
npx neon@latest cs <branch> --project-id <neon project id> --database-name <database> --ssl verify-full
```

Keep it in `backend/.env` (gitignored) under a name of its own, for example `NEON_ASPIRANT=` or
`NEON_BLANK=`. Never paste it into a command line that is logged or a file that is committed.

- `sslmode=verify-full` checks Neon's certificate and hostname. `require`, the Neon console's
  default, encrypts without checking who answered. asyncpg does not support channel binding, so
  the certificate check is what stops a machine in the middle.
- `backend/src/backend/config.py` rewrites a `postgresql://` URL for asyncpg: it names the
  driver, reads `sslmode` as `ssl` and drops `channel_binding`. The string goes in as Neon prints
  it, pooled (`-pooler` in the host) or direct.

## 2. Migrate

From `backend/`, with the database's string in `DATABASE_URL` (an environment variable wins over
`backend/.env`):

```bash
cd backend
export DATABASE_URL=$(grep '^NEON_ASPIRANT=' .env | cut -d= -f2- | tr -d '\r')
uv run alembic upgrade head
```

Run it before deploying code that needs a new migration. Each revision commits on its own, so a
failing one leaves the revisions before it applied.

**A database built from an older chain.** While there is no real data, the revisions are folded
into one from time to time under an ID no earlier revision used. A database built before that
answers `Can't locate revision identified by '<id>'` to `uv run alembic current`. Rebuild it;
this deletes every table and row in that database and runs only when `--yes` names it:

```bash
uv run campaign-crm reset-database --yes <database name>
uv run alembic upgrade head
```

Run without `--yes`, the first command only prints the name of the database it would empty.
Then load the data again (step 3).

## 3. Load the data, once per empty database

Still in `backend/` with `DATABASE_URL` set:

```bash
uv run campaign-crm seed            # 2022 geography: 47 counties ... 27,273 centres; a few minutes
uv run campaign-crm seed-results    # past results 2013 to 2022, which the vote targets read
```

`seed` on a database that already has counties prints "Reference data is already loaded" and
changes nothing; `--force` reloads it in place. A seed that stopped partway leaves counties
without centres, and only `seed --force` finishes it. `seed-results` skips a file it has already
loaded (`--force` reloads it) and then reworks the targets of every open campaign.

Then make the installation, one of two ways:

- **A demo**, ready to sign in to. One password for every login, at least 12 characters:

  ```bash
  uv run campaign-crm demo-install --password <demo password> --url https://<project>.vercel.app
  ```

  It builds David Otieno for Kasarani (MP) with the logins `admin` (superuser), `candidate`,
  `manager` and `mobilizer`, and prints their sign-in emails. `--sheet <file.md>` also writes
  them to a file. It refuses a database that is already set up.

- **A real installation**, set up through the browser. Print a one-time token (valid 24 hours,
  spent on use):

  ```bash
  uv run campaign-crm setup-token
  ```

  Open `https://<project>.vercel.app/setup`, paste it and follow the six steps.

## 4. Create and deploy the Vercel project

```bash
tools/deploy-demo.sh <project name> NEON_ASPIRANT
```

The second argument names the connection string in `backend/.env`. The script creates the
project if needed, links it, sets the variables below for Production, deploys, sets
`PUBLIC_URL` to the address Vercel gives, and deploys again. It never prints the connection
string. Re-running it redeploys and gives the project a new `SECRET_KEY`, which signs everyone
out.

| Variable | Value |
|---|---|
| `DATABASE_URL` | That installation's Neon connection string |
| `SECRET_KEY` | 48 random characters, different per project |
| `RECONCILE_HOURS` | `0` (functions run no background loop) |
| `CORS_ALLOW_ORIGINS` | `[]` (one origin) |
| `DEBUG` | `false` |
| `PUBLIC_URL` | The project's address; invite and reset links start with it |

Leave `DEFAULT_USER_PASSWORD` unset. When set, every login created for someone else gets that one
password instead of its own invite link.

To change or add a variable by hand, then deploy so it takes effect:

```bash
printf '%s' "<value>" | npx vercel@latest env add <NAME> production --force
npx vercel@latest deploy --prod --yes
```

Every other setting (email, payments, texts, calls) is listed with its meaning in
`backend/.env.example`.

## 5. Check it

```bash
curl https://<project>.vercel.app/health
```

answers `{"status":"ok","version":...}`. Then check the database itself, read-only: TLS, the
latest migration and the seeded geography (27,273 centres):

```bash
cd backend
LIVE_DATABASE=1 LIVE_DATABASE_URL="$DATABASE_URL" uv run pytest evals/test_live_database.py -s
```

Signed in as the superuser, the console's Health section shows the migration, the database and
each outside service's mode.

## Signing in and passwords

Every login signs in with its email and password at `/signin`. To give a login a password you
know, from `backend/` with `DATABASE_URL` set:

```bash
uv run campaign-crm reset-password -u <username> --password <new password>
```

Leave `--password` off and the command prints a generated one. Either way, every session that
login had is signed out. A new superuser:

```bash
uv run campaign-crm createuser -u <username> --email <address> --superuser --password <password>
```

The site is public and sign-in is rate limited per device, so use a long random password:

```bash
uv run --no-project python -c "import secrets; print(secrets.token_urlsafe(18))"
```

## Texts, calls and call alerts

Set these on the API wherever it runs (the Vercel project's environment variables, or the
server's `.env`). With none of them set, texts stay in practice mode and calls are off.

| Setting | Where it comes from |
|---|---|
| `SMS_PROVIDER` (sozuri), `SOZURI_PROJECT`, `SOZURI_SENDER_ID` and `SOZURI_API_KEY` | The Sozuri project (Manage API). Use the test project until going live; it has its own key and sender ID |
| `SOZURI_SIGNING_SECRET` (starts szs_), `SOZURI_AUTH_KEY` (starts szk_) | Manage API > Callback URLs > Webhook security, per project |
| `SMS_CALLBACK_SECRET` and `CRON_SECRET` | Generate each with `uv run --no-project python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` | LiveKit Cloud project settings (the URL starts `wss://`) |
| `VAPID_SUBJECT`, `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` | `uv run campaign-crm make-vapid-keys`, once per installation |

Then paste the callback URLs into each dashboard:

```
Sozuri delivery:  https://<api host>/api/sms/<SMS_CALLBACK_SECRET>/sozuri/delivery/
Sozuri inbound:   https://<api host>/api/sms/<SMS_CALLBACK_SECRET>/sozuri/inbound/
LiveKit webhook:  https://<api host>/api/livekit/webhook/
```

On Vercel the API host is the project's own address. Africa's Talking, when used instead, takes
`https://<api host>/api/sms/<SMS_CALLBACK_SECRET>/delivery/`, `.../inbound/` and `.../opt-out/`.

The first batch of a bulk text goes at approval. Later batches, and runs approved outside
08:00-18:00 Nairobi time, go when the queue is drained:

```bash
curl -X POST -H "Authorization: Bearer $CRON_SECRET" https://<api host>/api/internal/sms/drain/
```

No scheduler calls it yet; on Vercel Pro a cron entry in `vercel.json` can
(`{ "path": "/api/internal/sms/drain/", "schedule": "*/5 * * * *" }`; Hobby allows one run a day).
The route also answers `GET`, which is how Vercel's cron calls it. On a server of your own,
`campaign-crm sms-worker` drains every 30 seconds.

For the texting demo, add the demo person's two numbers at demo time (never committed):

```bash
uv run campaign-crm demo-comms --phone <demo phone> --phone <second phone>
```

## On a server of your own

`deploy/` runs the whole installation on one server with Docker Compose: Postgres 17, a one-off
`migrate` step, the app (the `Dockerfile` image, which serves the built SPA and the API on one
origin), a nightly backup and Caddy for HTTPS. `deploy/README.md` lists the files, and
`docs/handover/IT_Operations.md` walks through it:

```bash
cd deploy
cp .env.example .env        # then fill in the required lines
docker compose up -d --build
docker compose exec app campaign-crm seed
docker compose exec app campaign-crm seed-results
docker compose exec app campaign-crm setup-token
```

The compose file runs no SMS worker; run `campaign-crm sms-worker` beside it, or call the drain
route on a schedule, so later batches go out.

## Known gaps

- Vercel functions run nothing in the background: payments reconciliation runs only from the
  Payments page, and later SMS batches wait for a drain call.
- Vercel keeps no files, so an upload (logo, photo, document) on a Vercel install is not kept.
  Use image links, or the Docker install with `UPLOAD_DIR` on a disk that is backed up.
- Rate limits are counted in memory by each function instance, so they are looser on Vercel than
  on one server.
- Vercel's Hobby plan is for non-commercial use; an installation shown to buyers belongs on Pro.
- Neon's free plan suspends the database after 5 minutes idle. The first query after that waits
  for it to start; the engine's `pool_pre_ping` replaces connections the suspend closed. Vercel
  functions also sleep, so the first request after a quiet spell waits a few seconds.
- Backups on Neon's free plan are its restore window: 6 hours of history, capped at 1 GB, and
  one manual snapshot. Nothing here takes a copy elsewhere. The Docker install's nightly
  `campaign-crm backup` does not run on Vercel.
- The free plan allows 100 CU-hours of compute a month per project and 1 GB of storage. Past the
  compute allowance Neon suspends the database until the next month; data is kept.
