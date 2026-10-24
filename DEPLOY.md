# Deploying to Fly.io, on Neon

Each machine serves both halves: FastAPI answers `/api` and `/health`, and the
built SPA is mounted at `/`. One URL, one origin, no CORS. The database is the
`campaign_db` database on Neon project `mzigo_crm` (`patient-flower-76867840`),
branch `production`, in `aws-ap-southeast-1` (Singapore), next to the app in
Fly's `sin`.

Everything below is yours to run, in PowerShell, from the repository root
(the folder holding `fly.toml`). Blocks that need `backend\` enter it with
`Push-Location` and leave with `Pop-Location`. No command prints the database
password: each one passes it from the Neon CLI straight into Fly or a file.

## Before the first deploy

Install Node.js (for `npx`) from nodejs.org, then:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
iwr https://fly.io/install.ps1 -useb | iex
```

Open a new terminal so `uv` and `flyctl` are on the path, then sign in. Both
open a browser:

```powershell
flyctl auth login
npx.cmd -y neon@latest login
```

`uv` supplies Python and the backend's dependencies, so nothing else is needed.
Commands call `npx.cmd` rather than `npx`: Windows PowerShell 5.1 would run
`npx.ps1`, which its default execution policy blocks.

## 1. Set Fly's secrets

```powershell
$u = npx.cmd -y neon@latest cs production --project-id patient-flower-76867840 --database-name campaign_db --ssl verify-full
if ($u -like "postgresql://*") { flyctl secrets set --stage -a mzigo-crm "DATABASE_URL=$u" } else { "No connection string; run npx.cmd -y neon@latest login" }
Remove-Variable u
```

The Neon CLI gives the direct host (no `-pooler` in the name) with
`sslmode=verify-full`:

- `verify-full` checks Neon's certificate and hostname against `certifi`'s CA
  bundle. `require`, the Neon console's default, encrypts without checking who
  answered. asyncpg does not support channel binding, so the certificate check
  is what stops a machine in the middle.
- The direct host needs no pooler between one small app and the database. The
  pooled host (`--pooled`) works too, for the app and for `alembic upgrade head`.

`backend/src/backend/config.py` rewrites a `postgresql://` URL for asyncpg: it
names the driver, reads `sslmode` as `ssl`, and drops `channel_binding`. So the
string goes in as Neon prints it.

`SECRET_KEY` is set once per app. Check with `flyctl secrets list -a mzigo-crm`;
when it is missing:

```powershell
$k = uv run --no-project python -c "import secrets; print(secrets.token_urlsafe(48))"
if ($k.Length -ge 32) { flyctl secrets set --stage -a mzigo-crm "SECRET_KEY=$k" } else { "No key generated; is uv installed?" }
Remove-Variable k
```

`--stage` stores a secret without touching the running machines; it takes
effect at the next deploy (step 2). A machine woken from suspend keeps the
values it had. Without `--stage`, Fly makes a new release with the value at
once.

Leave `DEFAULT_USER_PASSWORD` unset on Fly. When set, every login created for
someone else (a mobilizer added by a manager, an aspirant or manager created
with a campaign in the console, an admin reset with no password given) gets
that one password instead of its own.

## 2. Deploy

```powershell
flyctl deploy --remote-only -a mzigo-crm
```

`--remote-only` builds on Fly's builder, so Docker is not needed locally. The
image is built from the files on disk, committed or not. The release command
runs `alembic upgrade head` before the new release takes traffic, so a failing
migration fails the deploy and the running machines keep the old release. Each
revision commits on its own, so revisions before the failing one stay applied.

## Commands on a Fly machine

Steps 3 and 5 run commands on a machine with `flyctl ssh console -C`.

`flyctl ssh console` needs a started machine. When it reports none, open
`https://mzigo-crm.fly.dev/health` first: a request starts one of the suspended
machines.

On Windows `flyctl ssh console -C` prints `Error: The handle is invalid` as it
tears the session down, after the command has already finished. Read the
output above it.

## 3. Load the data, once per empty database

`campaign_db` already holds the reference data and the demo, so this step is
only for a new database; step 5 covers signing in to the existing one. The
reference seed writes 27,273 registration centres and is too slow for a release
command. Running it from your machine (see "Working against Neon from your
machine") avoids the risk of a Fly machine suspending mid-run, since Fly does
not count an SSH session as traffic. On Fly:

```powershell
flyctl ssh console -a mzigo-crm -C "campaign-crm seed"
flyctl ssh console -a mzigo-crm -C "campaign-crm demo --password=<the-demo-password>"
```

`seed` on a database that already has counties prints "Reference data is
already loaded" and changes nothing; `--force` reloads it, updating rows in
place. A seed that stopped partway leaves counties without centres, and only
`seed --force` finishes it. The live check below (27,273 centres) shows
whether it completed.

`demo` deletes any earlier demo (the three demo usernames, the campaign they
run, and every other login on that campaign), builds it again, and prints the
logins. `--password` gives them all one password; without it each gets its own
generated one. The printed "Sign in at http://localhost:5173" means
`https://mzigo-crm.fly.dev` here.

## 4. Check it

```powershell
flyctl status -a mzigo-crm
curl.exe https://mzigo-crm.fly.dev/health
flyctl logs -a mzigo-crm --no-tail
```

## 5. Sign in

`campaign_db` holds the demo logins `aspirant`, `manager` and `mobilizer`, the
superuser `root`, who gets the admin console, and the logins of any campaign the
console has created. Their passwords were shown once, when they were made. To give one a
password you know:

```powershell
flyctl ssh console -a mzigo-crm -C "campaign-crm reset-password -u root --password=<new-password>"
```

Leave `--password` off and the command prints a generated one instead. Either
way, every session that login had is signed out. Running step 3's `demo` line
alone also resets the three demo logins, and replaces the demo campaign.

A new admin login:

```powershell
flyctl ssh console -a mzigo-crm -C "campaign-crm createuser -u <name> -r manager --superuser --password=<password>"
```

Always pass `--password` through `-C`. Without it `createuser` asks for one,
and `-C` gives the prompt no terminal: it warns that input may be echoed and
stores whatever arrives, which need not match what the sign-in form sends.

The deploy is public and sign-in is not rate limited, so use a long random
password. This one is letters, digits, `-` and `_`, which PowerShell and the
remote shell pass through unchanged:

```powershell
uv run --no-project python -c "import secrets; print(secrets.token_urlsafe(18))"
```

Then open `https://mzigo-crm.fly.dev` and sign in.

## Working against Neon from your machine

`backend/.env` holds the settings for `uv run` commands; it is gitignored. To
point it at Neon:

```powershell
Push-Location backend
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
$u = npx.cmd -y neon@latest cs production --project-id patient-flower-76867840 --database-name campaign_db --ssl verify-full
if ($u -like "postgresql://*") { (Get-Content .env) -replace '^DATABASE_URL=.*', "DATABASE_URL=$u" | Set-Content .env } else { "No connection string; run npx.cmd -y neon@latest login" }
Remove-Variable u
if ((Get-Content .env) -match '^SECRET_KEY=$') {
  $k = uv run --no-project python -c "import secrets; print(secrets.token_urlsafe(48))"
  (Get-Content .env) -replace '^SECRET_KEY=$', "SECRET_KEY=$k" | Set-Content .env
  Remove-Variable k
}
Pop-Location
```

Check the database, read-only: TLS, the latest migration and the seeded
geography.

```powershell
Push-Location backend
$env:LIVE_DATABASE = "1"; uv run pytest evals/test_live_database.py -s; Remove-Item env:LIVE_DATABASE
Pop-Location
```

Seed or rebuild the demo from your machine instead of through Fly. These write
to the production branch, and `demo` replaces the existing demo as described in
step 3:

```powershell
Push-Location backend
uv run campaign-crm seed
uv run campaign-crm demo --password=<the-demo-password>
Pop-Location
```

Without a password flag, a local `demo` gives every account
`DEFAULT_USER_PASSWORD` when `.env` sets it. `demo` stops without changing
anything when one of its three usernames belongs to a superuser.

## Known gaps

- Neon's free plan suspends the database after 5 minutes idle. The first query
  after that waits for it to start; the engine's `pool_pre_ping` replaces
  connections the suspend closed.
- Backups are Neon's free-plan restore window: 6 hours of history, capped at
  1 GB, and one manual snapshot. A mistake noticed the next day can only be
  undone back to that snapshot, if one was taken. Nothing here takes a copy elsewhere.
- The free plan allows 100 CU-hours of compute a month per project and 1 GB of
  storage. Past the compute allowance Neon suspends the database until the
  next month; data is kept.
- Fly's Depot builder can fail with `authentication handshake failed: EOF` or
  hang on "Waiting for depot builder". `--depot=false` builds on a Fly builder
  machine instead.
- The app runs on `shared-cpu-1x` 512MB machines (`flyctl machine list -a
  mzigo-crm` shows how many), suspended when idle (`auto_stop_machines =
  "suspend"`, `min_machines_running = 0`). A suspended machine bills its
  rootfs, not CPU. `flyctl scale count <n> -a mzigo-crm` sets the number;
  `min_machines_running = 1` in `fly.toml` keeps one running, billed for CPU
  and memory, while idle, from the next deploy.
- `flyctl launch` is left out: `mzigo-crm` exists. A new app is created with
  `flyctl launch --no-deploy --copy-config --name <new-name> --region sin`,
  and `<new-name>` replaces `mzigo-crm` in every command above and in
  `fly.toml`. Step 1 then points the new app at the same `campaign_db`; give it
  its own Neon database or branch unless sharing is intended.
