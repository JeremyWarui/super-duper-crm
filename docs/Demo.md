# The demo installs

Two installations, each one Neon database and one Vercel project serving the site and `/api`
from one address. They are for showing the product for a few minutes at a time; nothing real
goes in them.

| Install | Address | Vercel project | Neon database | What it is |
| --- | --- | --- | --- | --- |
| Aspirant demo | https://kasarani-demo.vercel.app | `kasarani-demo` | `demo_aspirant` | David Otieno for Kasarani: candidate page and campaign |
| Blank | https://setup-demo.vercel.app | `setup-demo` | `demo_blank` | Empty, for trying `/setup` from scratch |

The databases are in Neon project `mzigo_crm_fra` (`cold-firefly-78479992`, Frankfurt), branch `production`.
Their connection strings are in `backend/.env` as `NEON_ASPIRANT` and `NEON_BLANK`.

## Demo choices and what production uses instead

| Area | Demo | Production |
| --- | --- | --- |
| Hosting | Vercel: the frontend and the API as Vercel Services in one project | A Vercel project on the Pro plan, or a server of your own with the Docker Compose package in `deploy/` |
| Payments reconciliation | `RECONCILE_HOURS=0` (functions run no background loop; payments in settle by webhook or the status check) | `RECONCILE_HOURS=24` with Paystack live |
| Uploads | Not used: seeded content uses image links, and Vercel keeps no files | `UPLOAD_DIR` on a disk that persists and is backed up |
| SMS | Africa's Talking, live key (`AT_USERNAME=shabaha`, no sender ID): real texts, paid from the AT balance | The client's own Africa's Talking or Sozuri account and sender ID |
| Meetings | LiveKit Cloud project `shabaha` | The client's own LiveKit project |
| Payments in | Paystack test key (`PAYIN_PROVIDER=paystack`): real prompts, no money; test number `+254710000000` | Paystack live key |
| Payouts, email | Practice mode (Paystack refuses third-party payouts to a starter business) | Paystack live key on a registered business; SMTP |
| Bulk texts after the first batch | Drained by hand (`POST /api/internal/sms/drain/` with `CRON_SECRET`) | `campaign-crm sms-worker`, or a scheduler calling the drain route |
| Passwords | One easy password per install for every login | Each person's own password, set through their invite link |
| Rate limits | In memory, per Vercel instance, so looser | In memory on one server |

## Logins

Every login on the aspirant demo shares one easy password, kept out of the repository and
handed over with the demo. Emails are `<name>@demo.campaign.test`.

| Login | Who |
| --- | --- |
| `admin` | Site admin (the superuser) |
| `candidate` | David Otieno |
| `manager` | Campaign manager |
| `mobilizer` | Mobilizer |

## Rebuilding the demo database

From `backend/`, with the database's string in `DATABASE_URL`:

```bash
export DATABASE_URL=$(grep '^NEON_ASPIRANT=' .env | cut -d= -f2-)
uv run alembic upgrade head
uv run campaign-crm seed
uv run campaign-crm seed-results
uv run campaign-crm demo-install --password <12+ characters>
for u in admin candidate manager mobilizer; do
  uv run campaign-crm reset-password -u $u --password <the demo password>
done
```

## The Laikipia governor demo

`laikipia-demo` runs on its own database, `NEON_LAIKIPIA`. It is a county seat, so its team
works ward by ward across Laikipia, with 20 contacts in four wards. It has five logins: `admin`, `candidate` (Aspirant),
`manager` (Jeremy), `coordinator` (Mary Wairimu, Laikipia East) and `mobilizer` (Dennis,
Nanyuki). Build it with the commands above, using `NEON_LAIKIPIA`, `--demo laikipia`, and
`coordinator` added to the reset-password loop.

`demo-install` refuses a database that is already set up. To start again, empty it first:
`uv run campaign-crm reset-database --yes <database name>`, then the commands above.

## The blank install

`demo_blank` is migrated and seeded with the reference data only. To let someone try setup, print
a token (valid 24 hours, spent on use) and give it to them with the site's `/setup` address:

```bash
export DATABASE_URL=$(grep '^NEON_BLANK=' .env | cut -d= -f2-)
uv run campaign-crm setup-token
```

Setup has six steps; the **Target** step previews the seat target from past results, so load
them with `campaign-crm seed-results` after `seed`. To offer setup again afterwards, empty it
with `reset-database`, then `alembic upgrade head`, `campaign-crm seed` and
`campaign-crm seed-results`.

## Vercel projects

`vercel.json` at the repository root defines two services: `web` (the Vite app in `frontend/`,
deep paths fall back to `index.html`) and `api` (the FastAPI app, loaded from `backend/asgi.py`).
`/api/*` and `/health` go to `api`; everything else to `web`. `frontend/.env.production` builds
the app against `/api` on the same address.

`.vercelignore` uploads only `vercel.json`, `frontend/` and `backend/`, without `.env` files,
the virtualenv, uploads or tests.

`tools/deploy-demo.sh <project> <NEON_ASPIRANT|NEON_BLANK>` creates the project if needed,
links it, sets the variables below from `backend/.env` and deploys to production. It needs the
Vercel CLI signed in (`npx vercel login`). Each install is its own Vercel project with these
environment variables (Production):

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | that install's Neon connection string |
| `SECRET_KEY` | 48 random characters, different per project |
| `RECONCILE_HOURS` | `0` |
| `CORS_ALLOW_ORIGINS` | `[]` |
| `PUBLIC_URL` | the project's address |
| `DEBUG` | `false` |

## Texts and calls (about 8 minutes)

Before the demo: the Sozuri test project, LiveKit Cloud and the VAPID keys are set (see
`DEPLOY.md`, "Texts, calls and call alerts"), and the demo person's two numbers are added. The
numbers are typed at demo time and never committed:

```bash
uv run campaign-crm demo-comms --phone <demo phone> --phone <second phone>
```

That adds two consenting contacts in a ward with nobody else, and two drafts: one without the
candidate's name and one signed with it. Run the demo between 08:00 and 18:00 Nairobi time, or
show a run waiting for 08:00.

1. The demo person opens the field app link on their phone, signs in, installs it (Add to Home
   Screen) and taps "Enable call alerts".
2. Console, Messages: "Send test SMS" to the demo person; their phone receives it and the log
   shows Delivered.
3. Approve the draft without the candidate's name: approval is refused with the reason. Approve
   the signed draft: Bulk sends shows the run, the batch sent and the Delivered count.
4. Calls: "Start call", video. The demo person's phone shows the alert; they tap it and join.
   Talk, mute, switch the camera.
5. End the call for everyone, then start an audio-only call to show the low-data mode.
6. Calls lists both calls with who came and for how long.

## Known gaps

- Vercel functions and the Neon database both sleep when idle; the first request after a quiet
  spell waits a few seconds.
- Vercel's Hobby plan is for non-commercial use; a demo shown to buyers belongs on Pro.
- An upload on these sites (logo, photo, document) is not kept.
- No scheduler drains the text queue on the demos; a run larger than one batch, or one approved
  outside 08:00-18:00, waits until the drain route is called.

## Provider webhooks

Each provider dashboard points at the aspirant demo:

| Provider | Setting | URL |
| --- | --- | --- |
| Paystack (test mode) | Test mode webhook URL | `https://kasarani-demo.vercel.app/api/payments/paystack/webhook/` |
| LiveKit Cloud | Project webhook, signed with the project's API key | `https://kasarani-demo.vercel.app/api/livekit/webhook/` |
| Africa's Talking | SMS delivery reports callback | `https://kasarani-demo.vercel.app/api/sms/<SMS_CALLBACK_SECRET>/delivery/` |

`SMS_CALLBACK_SECRET` is in `backend/.env` and the Vercel project's environment.
