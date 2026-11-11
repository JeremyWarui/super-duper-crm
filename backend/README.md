# Campaign CRM - backend

FastAPI, SQLAlchemy 2.0 (async) and Pydantic v2, on Postgres (Neon in production). Managed with `uv`.

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
uv run campaign-crm reset-database --yes <name>   # empty a Postgres database; see DEPLOY.md
```

The admin commands run the same service as the admin console. A refusal prints
its reason and exits 1.

`seed` loads the IEBC 2022 register from `data/`: 47 counties, 290
constituencies, 1450 wards and 27,273 registration centres, with each county's
turnout. Ward names from the gazetted register and the centres file are matched
after folding punctuation, and a clipped name matches when only one ward fits.
Diaspora (48) and prison (49) rows are skipped. The files go through the same
boundary and register imports as the console's Imports page, so places match by
code on a reload and each load shows in the import history.

`demo` builds the Roysambu MP campaign with mobilizers, events and supporters on
some wards, and prints three logins, generated per run unless `--password` or
`DEFAULT_USER_PASSWORD` is set:

```
  aspirant     Candidate: the cockpit, adds mobilizers
  manager      Campaign manager: the full war room
  mobilizer    Mobilizer: one ward
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
| `POST /api/auth/login/` `…/logout/` | Username and password for a token; sign out. |
| `GET /api/counties/` `…/{id}/`, `/api/constituencies/`, `/api/wards/`, `/api/centres/` | Reference geography; a mobilizer sees one ward. |
| `GET /api/campaigns/` `…/{id}/` | The caller's campaign. |
| `POST /api/campaigns/{id}/generate_targets/` | Rebuild the targets after new data. |
| `GET POST /api/campaigns/{id}/signups/` | The campaign-wide sign-up link: its code, and opening or closing it; manager only. |
| `GET POST /api/join/{code}/` | No token. The public sign-up page behind an event's QR code or a campaign's link. |
| `POST /api/join/withdraw/{code}/` | No token. A supporter takes their details off the register; the same answer for any code. |
| `GET POST /api/targets/`, `PATCH DELETE …/{id}/` | The win number per unit. |
| `GET POST /api/mobilizers/`, `DELETE …/{id}/` | Who works which ward. |
| `GET POST /api/events/`, `DELETE …/{id}/`, `POST …/{id}/record/`, `…/{id}/invite/` | Events, attendance, SMS invitations. |
| `GET POST /api/supporters/`, `PATCH …/{id}/` | The supporter register, and placing someone at a centre. Nobody on the team deletes a supporter; they withdraw themselves. |
| `GET /api/strategy/?campaign=` | The computed dashboard. |
| `POST /api/users/`, `DELETE …/{id}/` | Mobilizer logins; the password is returned once. |
| `/api/admin/…` | The console; superusers only. |

A foreign key travels under the bare name (`ward`, not `ward_id`), and reads
carry the parent's name beside it. Every error is `{"detail": "<sentence>"}`.

### By organisation type

`site_settings.organisation_type` decides what exists. In an aspirant
installation the party office (`/api/party/members/`, `…/volunteers/`,
`…/aspirants/`, the dashboard and console), the party's own website pages
(leaders, organs, values, branches, results, join and withdraw, the candidates
directory) and their console editors answer 404, as if they were never
mounted. The website content both types share (posts, slides, issues,
documents, videos, places, subscribe) stays under `/api/party/`.
Party-only routes are `PartyOnlyRoute`s (`api/install.py`): the routers that
mix both kinds put them on a `party_router`. The `InstallationType`
middleware reads the type for any request shaped like a party route, and a
`PartyOnlyRoute` matches nothing outside a party installation, so any method,
body or missing slash gets the same 404 as an unknown path. The party inbox
task runs only in a party installation.

Campaign workspace access is decided in `services/access.py`: party and
standalone workspaces are always open; a hosted one is open while its aspirant
is approved, or when it has none.

The party workspace (`kind = 'party'`, national, no seat or candidate) is
created once by a superuser (`POST /api/party/workspace/`) with its first
Workspace Manager, and gets a target in every ward. Its coordinators read the
party members living in their area (`GET /api/party/workspace/members/`,
read-only, a page at a time, each page audited as `members.area_read`) and
hold one active recruitment code each (`…/recruitment/`; POST replaces it).
A Join the Party application carrying an active code records the coordinator
and the county of the applicant's ward; any other code is ignored, and
membership officers still decide every application. A coordinator of a
hosted workspace gets 404 on these routes. The dashboard counts the party
workspace apart from hosted ones.

A candidate page (`candidate_profiles`) belongs to a campaign, one each; a
hosted campaign's page also names its aspirant. A campaign's volunteers
(`models/volunteer.py`, `campaign_id` set) are read, moved, signed up and
withdrawn through `services/campaign_volunteers.py`; `services/volunteers.py`
handles the party's own.

## Rules

- **One campaign per login.** Every route that puts a login on a campaign
  refuses a second one, and a unique index on `campaign_members.user_id` refuses
  it in the database.
- **A campaign belongs to its candidate**, the member whose role is candidate; a
  partial unique index allows one.
- **Only a superuser creates a campaign**, from the console, with new logins for
  its aspirant and, optionally, its manager. Nobody signs up for a login.
- **A campaign runs its own team.** Its aspirant adds the one manager, or
  replaces them: the old manager comes off the campaign and their login is
  turned off. The aspirant and the manager add coordinators and comms
  officers (`POST /api/campaigns/{id}/team/`) and set a coordinator's wards and
  centres (`PUT …/team/{user}/area/`); they and a coordinator (in their area)
  add and remove mobilizers. A second manager is refused everywhere, the
  console included.
- **Only the superuser resets a password**, from the console or with
  `campaign-crm reset-password`. Nobody on a campaign resets a teammate's. A
  reset signs the person out.
- **In an MCA race a mobilizer works one registration centre with a target**,
  or none yet; a whole ward or an untargeted centre is refused.
- **Supporters sign themselves up and withdraw themselves.** `/api/join/{code}/`
  takes an event's code or the campaign's own link (`/api/campaigns/{id}/signups/`,
  which starts closed and only the candidate and manager read or open); the campaign link asks
  for a ward, or in an MCA race an optional centre, from the campaign. Every
  sign-up gets a withdrawal code, which only works for a new supporter, and
  `/api/join/withdraw/{code}/` answers the same for any code, so neither page
  shows whether a phone is on the register.
- **Only an admin deletes a campaign**, and that deletes everything on it and the
  logins of its people.
- **Scoping is by membership.** A campaign the caller is not on answers 404.
  Inside it, `services/permissions.py` maps each action to the roles that may do
  it and how far they reach: the whole campaign, a coordinator's area (their
  `campaign_member_areas` wards and centres), or a mobilizer's own ward. Routers
  guard with `require(action)` (`api/deps.py`); `api/scope.py` applies the reach
  to every read and write, and a place outside it answers 403.

| | Candidate | Manager | Coordinator | Comms | Mobilizer | Agent |
|---|---|---|---|---|---|---|
| Strategy | yes | yes | area | no | no | no |
| Read targets | yes | yes | area | no | own ward | no |
| Change targets | yes | yes | no | no | no | no |
| Add or replace the manager | yes | no | no | no | no | no |
| Team: coordinators, comms, areas | yes | yes | no | no | no | no |
| Read mobilizers | yes | yes | area | no | own ward | no |
| Add, move, remove mobilizers | yes | yes | area | no | no | no |
| Supporter register, read and write | yes | yes | area | no | own ward | no |
| Read events | yes | yes | area | yes | own ward | own |
| Schedule and record events, preview invites | yes | yes | area | no | own ward | no |
| Send event invites by SMS | yes | yes | no | no | own ward | no |
| Read payments | yes | yes | area | no | own | own |
| Schedule payments | no | yes | area | no | no | no |
| Release, cancel, mark payments | no | yes | no | no | no | no |
| Campaign volunteers | yes | yes | area | no | no | no |
| Delete a campaign, reach `/api/admin/` | no | no | no | no | no | no |

## The admin console

A superuser (`createuser --superuser`) gets `/api/admin/`: every campaign with
its team, wards and size; every login and its campaign; rename and delete a campaign; add and remove members; create a
login; reset a password; disable or enable a login. An admin cannot disable themselves or the last active superuser,
and a superuser is never put on a campaign.

The console makes no campaign. An aspirant copy's one workspace is made at setup
(`POST /api/setup/`); a party copy's hosted workspaces are made from approved aspirants
(`POST /api/party/aspirants/{aspirant_id}/workspace/`).

## The workspace website (aspirant installations)

In an aspirant installation the Candidate, the Manager and Comms edit the
website from the workspace under `site.write`: `/api/workspace/site/settings/`
(GET, PUT) and the posts, slides, issues, documents and videos under
`/api/workspace/site/{kind}/` (GET, POST, and PATCH or DELETE on `{id}/`).
They call the services the console uses, so the same checks apply (colours must
pass the contrast check) and every edit is audited. These routes are
`AspirantOnlyRoute`s (`api/install.py`) and answer 404 in a party installation,
where the website is edited from the console and the party office.

In an aspirant installation the homepage is the standalone campaign's
candidate page: `GET /api/site/candidate/` (404 until published) and
`POST /api/site/volunteer/`, which signs a volunteer up to the campaign
(`services/campaign_page.py`); the workspace edits it at
`/api/workspace/site/candidate/`. The site settings carry
`payment_instructions`, which the Contribute page shows; the site takes no
money. The news sign-up's consent wording follows the installation type
(`consent.subscribe_wording`), and is the text recorded with each sign-up.

## Uploads

A superuser uploads a file with `POST /api/files/` (multipart: `file`, `area`,
`public`). JPEG, PNG and WebP images up to 5 MB are decoded and re-encoded at
480, 960 and 1920 pixels wide (or the original width when narrower), which
drops their metadata, location included. PDFs up to 10 MB are kept as sent. The
type is read from the content and must match the type the file was sent as.
Files live in `UPLOAD_DIR`; `stored_files` records each one.
`GET /api/files/{id}/` (add `?w=` for a narrower image) serves a public file to
anyone with a year-long cache, and a private one only to a superuser, as 404 to
everyone else. `site_settings`, `hero_slides`, `party_leaders`,
`party_documents` and `candidate_profiles` each have a `*_file_id` beside the
`*_url` they keep as a fallback.

The website editors' image fields upload with a Choose file button and keep the
file's `/api/files/{id}/` address; image fields accept that address or an
`https://` one. An aspirant workspace uploads public images at
`POST /api/workspace/site/images/` (multipart: `file`, `area`) under `site.write`.

## Post text

A post's `body` is HTML from the website editor (Tiptap). On save,
`services/rich_text.py` keeps only paragraphs, line breaks, two heading levels,
bold, italic, strikethrough, links (`https:`, `mailto:` or a page on this
site), bulleted and numbered lists, quotes, and images from `https://` or this
site's uploads; every other tag, attribute and script is removed. Post reads
carry `excerpt`, the opening 300 characters as plain text, and `read_minutes`
counts the words without the tags. The public post page sanitizes the HTML
again (DOMPurify) before drawing it.

## Texts to supporters

Every text goes through `services/texting.py`, which leaves out numbers that
opted out and writes one `sms_log` row per number: `practice` (nothing sent),
`sent` (the gateway took it), then `delivered` or `failed` from the delivery
report, with the gateway's reason. Texts to supporters end with "Reply STOP to
opt out." and go only to supporters with `consent_given` and a usable number.

- **Messages** (`/api/messages/`, the workspace's Messages page): the
  Candidate, Manager, Coordinators and the Comms officer draft (`sms.draft`);
  only the Candidate or Manager sends (`sms.send`), either their own text at
  once or a draft by approving it. A draft goes to the wards picked, or every
  ward the drafter reaches, and always only inside the drafter's area as it is
  when the draft is approved. A draft is sent or declined once. The sender
  sees each message's delivery log.
- **Event invitations**: `POST /api/events/{id}/invite/` texts an event's
  consenting supporters, sets `number_reached` on a real delivery, and logs
  each number against the event. `dry_run` works out the recipients and cost
  and is open to anyone who may change the event; sending is `sms.send`.
- **STOP**: a reply starting STOP (or STOPALL, UNSUBSCRIBE, END, QUIT, CANCEL,
  ACHA) opts the number out of the campaign that last texted it, or the whole
  installation if none has. A number on the gateway's own opt-out list is
  handled the same way. Each incoming text is kept once per gateway id.
- **Callbacks**: Africa's Talking does not sign its callbacks, so each URL
  carries `SMS_CALLBACK_SECRET`; a wrong or missing secret gets 404. Set these
  in its dashboard, rate limited to 6,000 a minute per client:

  ```
  https://<api host>/api/sms/<secret>/delivery/   delivery reports
  https://<api host>/api/sms/<secret>/inbound/    incoming messages
  https://<api host>/api/sms/<secret>/opt-out/    bulk SMS opt-out
  ```

  A repeated report changes nothing, and a report after `delivered` or
  `failed` is ignored.

Sending for real needs:

```bash
SMS_PROVIDER=africastalking
AT_USERNAME=your-username     # or "sandbox"
AT_API_KEY=<africas-talking-api-key>
AT_SENDER_ID=                 # blank uses the shared short code
SMS_CALLBACK_SECRET=<long random string>
```

The console's Health tab shows the SMS mode, and its test button (and the
setup wizard's) sends a logged test text.

## First-run setup

A new database has no site settings, so every `/api` route except `/api/setup/*` answers
503 with `code: not_set_up`, and the SPA sends every page to `/setup`. `/health` still answers.

```bash
uv run alembic upgrade head
uv run campaign-crm seed            # counties, wards and centres, for an aspirant's seat
uv run campaign-crm setup-token     # prints a token: valid 24 hours, one use
```

Open `/setup` and paste the token. The six steps set the organisation type (fixed for good),
the name, logo link and colours (contrast checked), contacts and privacy notice, the first
superuser, and then either the aspirant's seat, area, election date and candidate login, or
optionally the party workspace and its Workspace Manager. `POST /api/setup/` makes all of it
in one transaction, audited as `setup.completed`; a refused request writes nothing and leaves
the token unspent. Afterwards the summary lists the email, SMS and payout providers `.env`
picks, with a test email and text sent to the signed-in superuser.

A database that has never had a login loses the placeholder settings row on migration, so it
opens the setup; one with logins keeps its settings.

### Known gaps

- Payouts: the List Transfers reply shape (`reference`, `status`, `amount`,
  `transfer_code`, `meta.pageCount`) follows Paystack's API as known, not a
  fetched copy of its docs; confirm against a live account before relying on
  reconciliation. Two releases at once can both pass the balance check, and
  Paystack then refuses the second as a failed transfer. A difference with no
  payment (a transfer under this app's reference that matches nothing) is
  recorded but shown on no campaign's page. Fees are fixed in code, so a
  Paystack price change needs a code change.

- Texts: Messages go to supporters only, not to the team and mobilizers, and
  are sent now, not scheduled; the gateway's credit balance is not shown. The
  footer and part count assume plain GSM text: a message with an emoji or
  other Unicode is billed in shorter parts than the page shows. STOP from a
  number no campaign has texted opts it out of every campaign. An opt-out
  cannot be undone from the app. A send is made while the approval holds its
  row, so a gateway that hangs holds it for up to 30 seconds.

- The logo is an https link; uploaded logos wait for the site editor to use stored files.
- Invite emails go out before the setup commits; if the commit then fails, the link is dead.
- Restore is proven against a backup this version made; a backup from an older version
  (an earlier migration head) has not been restored in a test.
- Payments in: Paystack does not document the `charge.success` payload beyond the fields
  read here (reference, status, amount, currency); `receipt_number` is taken when present.
  No receipt is emailed or texted. Marking a fee paid by hand leaves a code the member
  reported still waiting on Payments in, to reject. Contributions are listed but not part of
  any declaration export.
- A visitor can send an M-Pesa prompt to any phone number; the owner must still enter their
  PIN, and each device is limited to 10 payment starts an hour.

## Reference data imports

Boundary reviews and new voter registers load from CSV, from the server or the console's
"Areas and register" tab. Samples covering Lamu County are in `docs/handover/samples/`; on a
freshly seeded database both report "no changes".

```bash
uv run campaign-crm import-boundaries docs/handover/samples/boundaries.csv --dry-run
uv run campaign-crm import-register docs/handover/samples/register.csv
```

- **Boundaries** (`county_code, county_name, constituency_code, constituency_name, ward_code,
  ward_name, centre_code, centre_name`): one row per centre, or per ward with the centre columns
  blank. Counties, constituencies and wards match by their code, a centre by its ward's code
  and its own. Names change, wards and constituencies move, new areas are created. A file covers
  whole counties: a constituency or ward it leaves out of a county it names is retired, and so
  is a centre left out of a ward it lists centres for. Nothing is deleted; a retired area keeps
  everything that refers to it, is hidden from pickers and from new targets, and comes back if a
  later file names it again.
- **Register** (`county_code, ward_code, centre_code, registered_voters, turnout_pct`): a county
  row sets its voters and turnout, a ward row its voters, a ward and centre row the centre's.
- Every row is checked first; one bad row and nothing is written. `--dry-run` (or "Check file")
  reports every change and writes nothing. A real run is audited (`import.boundaries`,
  `import.register`) and keeps one `import_changes` row per change under its `import_runs` row.
- Each target stores the registered voters its win number was worked out on, so an import
  changes no figure on the Targets, Strategy or Overview pages. A candidate or manager presses
  **Refresh targets** (`POST /api/targets/refresh/`) to take the current register: every win
  number is recomputed, new units get targets, and each target keeps its turnout and committed
  votes. Turnouts are the campaign's own estimates; an imported county turnout is the starting
  turnout for targets created after it.

### Known gaps

- A boundary file covers whole counties; a file listing one ward retires the rest of its
  county. The check step shows every retirement before anything is written.
- A register file may set numbers on retired areas.
- Codes are not unique in the database; the seed loads them unique, and imports match on them.

## Operating the installation

The console (`/console`, superusers only) has **Health**, **Audit** and **Export** tabs beside
the campaign, login, party and area tabs.

- **Health:** version and migration state, whether the database answers and its size, the
  organisation type, each outside service from `.env` (configured, or "not configured" and
  running in practice mode), the last backup, and free disk space for uploads and backups. A
  test SMS goes to any number; a practice payout of KES 1 runs only while payouts are in
  practice mode, never where they move real money.
- **Audit:** the audit trail, newest first, filtered by the start of the action (`import`
  finds every import), part of the person's name, and a date range. Read-only.
- **Export:** every table as JSON and CSV in one zip, with `manifest.json` listing the row
  counts. Sign-in tokens, invite and setup links, and password hashes are left out. Each
  export is audited.

```bash
uv run campaign-crm backup        # pg_dump + uploads -> BACKUP_DIR/backup-<UTC time>.tar.gz
uv run campaign-crm restore backups/backup-20261106-135543.tar.gz --yes-erase-current-data
uv run campaign-crm export --out records.zip
```

- `backup` needs `pg_dump` (set `PG_BIN_DIR` when it is not on PATH, e.g.
  `C:/Program Files/PostgreSQL/18/bin`). It records each run in `backup_runs`, and keeps the
  newest archive of each of the 14 latest days and each of the 8 latest weeks. Run it nightly
  from cron, then copy `BACKUP_DIR` off the server:
  `15 2 * * * cd /srv/app/backend && uv run campaign-crm backup && rsync -a backups/ offsite:backups/`.
- `restore` refuses without `--yes-erase-current-data`. It restores the database with
  `pg_restore --clean` in one transaction, moves the current uploads aside to
  `uploads.before-restore-<time>`, and puts the archive's in place. Restart the app after.

## Branch officials

Each county branch's officials are terms in `branch_officials`: an office (chairperson,
secretary, treasurer, organising secretary, youth leader, women leader, or a named other
office), the approved party member holding it, the first and last day, why it began and
ended, and optionally the signed minutes as a private upload. The Membership Officer and the
superuser keep them from the party CRM's Branches page; the superuser also edits the branch's
office, next meeting and whether it is published.

- Only an approved member can be appointed. Appointing someone ends the office's current term
  the day before the new one starts, so an office has one holder at a time; a term already
  starting on or after that date has to be ended first. "Other" offices may run side by side.
- A term ends early as resigned, removed or completed; the office is vacant from the next day.
- The public branch pages and the home page name only the officials in office today.
- The chairperson and secretary text that branches used to hold became terms on migration,
  linked to the one approved member with that name, or kept as the name with a note.
- Every appointment, ending and minutes upload is audited.

The officials mockup sends changes to HQ for approval. Here the people editing are HQ (the
Membership Officer and the superuser), so changes apply at once and the audit trail records them.

## Applying to vie

A nominations timetable (`nomination_windows`) has a title, the days applications open and
close, the requirements, and the seats on offer with each seat's fee in KES. The Nominations
Officer or the superuser drafts and edits it on the Aspirants page; only the superuser publishes
it, and never a timetable they drafted or last changed. A published timetable cannot change, cannot have closed
already, and cannot overlap another published one. The public Vie page shows the current or next
published timetable (`GET /api/party/nominations/current/`).

A member applies from their account's "My nomination" tab (`/api/party/nominations/mine/`):

- Only an approved member applies, only while the timetable is open, only for a seat it offers,
  and only with no other live nomination. The area is their own ward, its constituency or its
  county, by seat.
- The application starts as a draft. The member attaches documents (PDF or photo, private
  uploads), and the nominations office marks the fee paid with its M-Pesa or bank reference.
  The member submits it with the declaration only once any fee is marked paid and before the
  timetable closes.
- An officer cannot move a member's draft to submitted, and cannot decide their own
  application. Approval is always an officer's decision on the Aspirants page; nothing is
  approved automatically.
- The member withdraws a draft or submitted application. Every step is audited.

## Shared counts with the party

The party never reads a campaign's supporters, except counts the campaign has chosen to share.
A hosted workspace's "Party feed" page (`/api/party-feed/?campaign=`, for the Candidate, the
Manager and Comms) shows the party's published events and statements for the campaign's county
or the whole country, and the party's approved members counted per ward of the seat. Its three
switches, all off until the Candidate turns one on (`sharing.write`), decide what the
superuser's dashboard reads from `/api/party/shared/`:

- **Event reach**: done events, and the numbers reached and attended.
- **Ward coverage**: how many wards of the seat have a mobilizer, ward by ward.
- **Supporter counts by ward**: numbers only.

The counts are worked out on each read and kept nowhere on the party side, so a switch turned
off shows "Not shared" on the next read. Each change is audited and listed on the page. The
party workspace and a standalone workspace have no such page (404).

## Party texts to members and volunteers

The Comms Officer, a party office like the others, drafts texts on the party CRM's Messages page
(`/api/party/messages/`) to members or volunteers, everywhere or in one county or ward, and sees
how many people the draft reaches. Only the Party Super Admin sends one, and never a draft they
wrote; a draft is sent or declined once. Sending goes through `services/texting.py`, so every
number gets an `sms_log` row with `purpose = 'party'` and the message's id, and the page shows
how delivery went.

- **Members** get a party text only if they ticked the join form's optional "Send me party
  updates by SMS" box; the wording and time are kept on the member. Members who joined before
  the box existed, or whom an officer added, are not texted.
- **Volunteers** get one only while active and only if they chose SMS as their contact.
- A STOP reply after a party text opts the number out of every text from this installation,
  party and campaigns alike, because the party is not a campaign.

## Personal data

`services/privacy.py` holds the work a buyer owes the people on its registers under the Data
Protection Act 2019.

- **Erasing on request** blanks a row's personal fields and keeps the row, so ward counts,
  support levels and totals stay right. The name becomes "Erased", phone numbers, emails, ID
  numbers, notes and withdrawal codes are cleared (a unique phone or ID number becomes a `~`
  placeholder that no real number matches), the number is blanked on the row's past texts in
  `sms_log`, and a login left behind with no campaign is emptied and switched off. One audit row
  per erasure names only the row, the officer and the time. An erased row cannot be erased again
  or edited.
  - In a workspace the Candidate or Manager erases any supporter, a withdrawn volunteer, or the
    sign-up of a mobilizer or agent who was turned down or has left the team (its ID number
    included): `/api/campaigns/<id>/data/...`.
  - In the party the Membership Officer erases a withdrawn or rejected member (with their
    volunteer profile and account) or a withdrawn volunteer profile.
- **Every supporter has a withdrawal code.** One a mobilizer registers gets it texted through
  `services/texting.py` (`purpose = 'withdrawal_link'`); the Supporters page shows the link and
  can text it again. The `data_protection` migration gives a code to every supporter who had none.
- **Data requests** (access, correction, erasure) are logged per workspace and for the party,
  due 7 days after receipt for access and 14 for correction or erasure (Data Protection
  (General) Regulations 2021, regulations 9, 10 and 12); the officer can move the date. Marking
  one answered needs a note of how.
- **Closing a campaign** (the Candidate, never the party workspace) makes it read-only: every
  write by its team is refused except sign-out and the data routes, and its public sign-up and
  team links stop taking people. After the retention period (default 6 months, set before
  closing) the Candidate can erase every supporter's personal data in one action. Nothing is
  erased on a timer.

### Known gaps

- Payments keep the payee's name and number, as financial records. A party member's past
  aspirant applications and audit rows written before this ticket are not blanked.
- The party member and volunteer CSV exports list erased rows with the placeholder number.
- The due dates follow the regulations as published; have counsel confirm them for the buyer.
- A superuser's admin routes are not held by a closed campaign's read-only rule. Replies kept in
  `sms_inbound` and the bodies of past texts are not blanked on erasure.

## Sign-in links

Nobody is shown a password. A new login gets an emailed invite link (72 hours)
to choose its own; "Forgot your password?" on the sign-in page emails a reset
link (1 hour), and so does the console's Send reset link. A link works once,
only its SHA-256 is stored (`login_invites`), and using it signs the login out
everywhere else. A login with no email gets no link: add one with
`campaign-crm set-email`, then send a reset link. The reset request answers
the same for any address and is limited to 5 an hour per device and 3 per
address.

Every email is recorded in `email_log`, with the link's token replaced by
`[removed]`. The default `EMAIL_PROVIDER=practice` sends nothing and writes the
whole email, link included, to the backend's log: in development, copy the
link from the terminal running the API.

Real email needs:

```bash
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.example.com
SMTP_PORT=587                 # 465 for TLS from the start
SMTP_USER=<smtp-user>
SMTP_PASSWORD=<smtp-password>
SMTP_FROM=Campaign <noreply@example.com>
PUBLIC_URL=https://your-app.example.com
```

`campaign-crm reset-password` still sets a password directly, for the operator
locked out of the superuser login.

## Google sign-in

Sign-in is email and password. Google sign-in (`services/oidc.py`, OpenID Connect
with PKCE) is off, and its button hidden, until both keys are set:

```bash
GOOGLE_CLIENT_ID=<id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<secret>
PUBLIC_URL=https://your-app.example.com
```

In Google Cloud, make a "Web application" OAuth client whose authorised redirect
URI is exactly `PUBLIC_URL` + `/api/auth/google/callback/`, trailing slash
included. It signs in only an existing login whose email matches a Google email
Google has verified, and never creates one. Every sign-in and every refusal is
in the audit trail (`login.google`, `login.google_refused`).
The console's Check Google sign-in button confirms Google answers.

## Team sign-up and agents

Each workspace has a team link, `/team/<code>` (`campaigns.team_code`), with a
QR code on the Sign-ups page. A mobilizer picks a ward (a centre in an MCA race),
an agent a registration centre, and both give name, phone, email and ID number
with consent. That makes a `team_registrations` row and a pending login that
cannot sign in. The candidate, the manager, or a coordinator in whose area the
place lies approves it (the login is activated, the person joins as a mobilizer
or an `agents` row, and an invite link is emailed) or rejects it with a reason
(the login is deleted and the ID number blanked). Phone and ID number are unique
per workspace among sign-ups not rejected. ID numbers reach only the candidate,
the manager and the person themselves; `GET /api/agents/export/` gives the
candidate and manager a CSV per centre for appointment letters.

## Assignments and payment approval

Mobilizers and agents are paid only for work assigned to them and marked done
(`/api/assignments/`): an event, ward work, or an activity with a description,
each carrying its amount and its ward (and centre), so a coordinator's area
covers it. A payment is scheduled against one done assignment, for its amount,
once (`uq_payments_assignment`). Whoever schedules never approves
(`services/payment_routing.py`): a coordinator's payment waits for the manager,
a manager's for the candidate; in the party workspace only coordinators
schedule and the Workspace Manager approves. Approving releases it through the
payout provider; the approver can also mark it paid by hand or decline it with
a reason. Every schedule, approval, decline and not-sent is audited.

## Payouts

Approving a payment to a mobilizer or agent (`/api/payments/`) releases it
through the payout provider. The default, `practice`, moves no money, marks
each release paid under a `PRACTICE-` reference, and shows a made-up balance
of KES 500,000 with no fees. Real M-Pesa transfers through Paystack need:

```bash
PAYOUT_PROVIDER=paystack
PAYSTACK_SECRET_KEY=<paystack-secret-key>
PAYSTACK_WEBHOOK_SECRET=<whsec-signing-secret>   # blank: legacy x-paystack-signature
```

and the Paystack webhook pointed at `/api/payments/paystack/webhook/`.

- **Balance first.** Every release reads the Paystack balance and is refused,
  before any transfer, when it does not cover the amount and the fee (KES 20
  up to 1,500, 40 up to 20,000, 60 above, per paystack.com/ke/pricing). The
  release form shows the balance, the fees and what is left
  (`POST /api/payments/release-check/`). Money is added in the Paystack
  dashboard.
- **The webhook decides.** A transfer Paystack accepts stays `sending` until
  `transfer.success`, `transfer.failed` or `transfer.reversed` arrives for
  that attempt's reference (`pay-<id>-<attempt>`). A repeated event changes
  nothing. A failed or reversed transfer goes back to "To retry" with
  Paystack's reason, and approving it again sends a new attempt.
- **Reconciliation.** Once a day (`RECONCILE_HOURS`, 0 turns it off), and on
  "Check now" on the Payments page, `services/reconcile.py` compares the last
  30 days of Paystack payments with Paystack's transfer list and records each
  difference: paid here but not there, paid there but not here, a different
  amount, an earlier attempt also paid, or a transfer under this app's
  reference with no payment. It changes no payment; the Candidate and Manager
  see their campaign's differences and settle them by hand.

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

The schema is built by the chain of revisions in `alembic/versions/`, oldest first,
each named `YYYYMMDD_HHMM-<revision id>.py`. Every revision runs on both Postgres and
SQLite, so test both lanes after adding one (see `docs/handover/Developer_Guide.md`).

```bash
uv run alembic revision --autogenerate -m "what changed"
uv run alembic upgrade head
uv run alembic upgrade head --sql        # print the SQL
```

`tests/test_migrations.py` fails when the models and the migrations disagree.

## Configuration

Read from the environment and `.env`; see `.env.example`. `SECRET_KEY` is
required and at least 32 characters.

## Known gaps

- Google sign-in matches a login by its verified email, as the design asks;
  Google advises keying on the account's `sub`. Someone who takes over an
  email address and gets Google to verify it for a new account signs in as
  that login. Storing `sub` at the first Google sign-in would close it.
- Coordinator, Comms and Agent have permissions but no screens yet (PD-10);
  `createuser` offers only candidate, manager and mobilizer. An agent's "own"
  rows (events, payments) are empty until assignments exist (PD-37). The
  team API refuses an area for anyone but a coordinator; the database does
  not. Coordinators and comms officers are removed by an admin, not from the
  Team page. Downgrading `campaign_roles` turns a pending login into a plain
  inactive one.
- The map holds only the actions a route serves today; `team.approve`,
  `agents.*`, `team.id_read`, `assignments.write`, `sharing.write`,
  `site.write` and `export` arrive with their routes. Payment release stays
  with the Manager until approval routing (PD-37).
- One row differs from section 0.2 by decision: a Mobilizer reads targets
  in their own ward. `mobilizers.read` is not a row
  there; it keeps who reads the mobilizer list as before, plus coordinators
  in their area. A coordinator cannot set a mobilizer to no ward, as a place
  with no ward is outside every area.
- A coordinator sees payments through their events' places, so a payment
  with no event never shows to them. `area_ids` reads the caller's areas
  without naming the campaign; one campaign per login keeps that exact.
- The workspace website's editors cannot upload files: uploads are for a
  superuser (`/api/files/`). Its public Events page lists event posts; the
  workspace's own events are not published to it.
- Uploads: the `*_file_id` columns are not yet set or read by any editor or
  page (PD-9, PD-22); the request body is read in full before the size check,
  so the limit guards storage, not memory; a file nothing points to is never
  removed, and the same file uploaded twice is kept twice. A PDF is checked by
  its start and end markers only and is served inline (in a CSP sandbox). A
  private file is for superusers only until receipts arrive. HEAD on a file
  answers 405.
- The party workspace: the member register lists members of every status; the
  dashboard's seat filter does not narrow its totals or the recruitment counts;
  a member who reapplies takes the recruiter of the new application, or none;
  the admin console builds the workspace's ~1,450 ward rows on each list.
- The website editor lists every approved aspirant but saves a candidate
  page only for one with a workspace; it does not mark the others. Saving a
  page for an aspirant whose campaign already holds a page with no aspirant
  fails at the database (500), and a page keeps its campaign if the
  aspirant's link ever changes; neither happens through today's flows.
- `tests/test_boundaries.py` reads import statements only: a star import,
  `importlib`, or reaching party code through a package attribute
  (`models.party.X`) is not caught, and a new campaign module must be added
  to its `CAMPAIGN` list by hand.
- The `InstallationType` middleware matches the raw request path, so serving
  the API under a path prefix (`root_path`) hides party routes in a party
  installation too.
- Code that prints a campaign's seat (`api/routers/campaigns.py`,
  `api/routers/targets.py`, `services/admin.py`) assumes one is set. A party
  workspace has none; PD-7 creates the first.
- Applying to vie: a member's area comes from their ward, with no way to vie elsewhere. A
  rejected or withdrawn application drops out of their account, and they may apply again
  while the timetable is open; there is no appeal step. The timetable has no IEBC deadline
  check, reduced fees, nomination method, rules PDF, SMS notice or dates-only-move-later rule
  from the mockup.
- Party texts: a STOP reply after a party text opts the number out of campaign texts too.
  There is no scheduling, test send, member groups (youth league, branch officials) or SMS
  credit balance from the Communications mockup.
- Party texts: a STOP reply after a campaign text opts the number out of that campaign only, so
  party texts still reach it. The recipient list is worked out again at send time, so the number
  sent can differ from the count shown when the draft was written.
