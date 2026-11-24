# Campaign CRM: system overview

What one installation is, who uses it, what it does, and how it is built. How to run the code
lives in the READMEs and `DEPLOY.md`; this document says what the code is for.

Last checked against the code: 24 November 2026.

Source paths are under `backend/src/backend/` unless they start with `frontend/`, `backend/`,
`contracts/`, `deploy/` or `tools/`.

---

## 1. What it is

An installation is **one candidate contesting one seat**: MCA, MP, Women Rep, Senator, Governor
or President. It holds exactly one campaign.

The campaign gets one number to chase, the **seat target**: the votes it needs, worked out from
past results (section 4). The target is shared out to the places the team works:

- an MCA race is worked **registration centre by registration centre**, inside its one ward;
- every other seat is worked **ward by ward** (a President race over all 1,450 wards, grouped
  by county).

The team records the work that moves those numbers: mobilizers and agents in the field, events,
contacts signed up, texts, calls and payments. The **strategy read** (`services/strategy.py`)
reads it all back on every request: progress per unit, the biggest gaps, units with nobody
working them, and what to do next. Nothing in it is stored, so the screen never disagrees with
the rows underneath it.

**Progress is supporters, not activity.** A unit's progress is the number of contacts at support
level **Supporter** filed under it, divided by its target. Undecided and Opposed contacts, event
attendance and texts sent do not count. Events shape the advice, not the score: the notes name
the unit with the biggest gap, say whether it has had events or a mobilizer, and tell the team to
ease off a unit that has met its target after 4 or more events.

---

## 2. Who uses it

Every login signs in with email and password, or with Google when it is configured. A campaign
login holds one role (`models/enums.py` `UserRole`). What each role may do, and how far it
reaches, is one table: `services/permissions.py` `MAP`. Reach is `all` (the whole campaign),
`area` (a coordinator's assigned wards and centres) or `own` (a mobilizer's ward, an agent's
centre). A role the table leaves out of an action is refused with a plain reason.

| Role | What they do |
|---|---|
| **Candidate** | Owns the campaign. Full access: targets, team, contacts, texts, calls, payments, the website, personal data. Adds or replaces the one manager, approves the manager's payments, and alone closes the campaign. |
| **Manager** | Runs the day to day with full access. Schedules payments (the candidate approves them) and approves coordinators' payments. |
| **Coordinator** | Works an assigned area of wards and centres: events, mobilizers, agents, assignments, contacts and team sign-ups there; drafts texts and starts calls for that area; schedules payments. |
| **Comms** | Reads events and targets, tries turnout scenarios, drafts texts, starts calls and edits the website. Sees no contact register. |
| **Mobilizer** | Works one unit: a ward, or a centre in an MCA race. Records events, adds contacts in their ward, sees their own payments. |
| **Agent** | A polling agent at one centre: their centre, assignments, events and payments. |
| **Superuser** | Runs the installation from the console at `/console`. Has no campaign role and never sits on the campaign; a signed-in superuser always lands on the console. |

The candidate's login is made at setup; the console refuses to make another.

---

## 3. First-run setup

Until setup has run, every API route but `/api/setup/` answers 503 `not_set_up`
(`api/install.py` `SetupGate`) and the browser is sent to `/setup`. The wizard is
`frontend/src/pages/setup/Setup.jsx`; the server side is `services/setup.py`.

It opens with a **setup token**, printed on the server by `campaign-crm setup-token`. A token
works once and for 24 hours; printing a new one retires any unspent one. Then six steps:

| Step | Asks for |
|---|---|
| 1. Name and colours | Site name, short name, logo link (`https://` only), primary and secondary colour. Colours that fail the contrast check are refused. |
| 2. Contacts | Contact email, phone, address, and the privacy notice shown on `/privacy` and at every sign-up form. |
| 3. First superuser | Username, email and password of the first console login. |
| 4. Campaign | Campaign name, seat, election date, the area (county, constituency or ward as the seat needs; none for President), and the candidate's login. |
| 5. Target | Nothing to enter. Shows the seat's past results, the winner's share, the typical winner, the reliability label, two-candidate or crowded, each turnout scenario with its majority line and target, and the split to wards (or centres). |
| 6. Check and finish | A summary; **Finish setup** runs it. |

Step 5 calls `POST /api/setup/target-preview/` (`services/target_preview.py`). It saves nothing
and uses the same calculation (`services/targets.py` `plan_targets`) that Finish saves, so the
saved targets equal the preview at the Expected scenario.

Finish (`POST /api/setup/`) spends the token and, in one transaction, writes the site settings,
the superuser, the campaign with its targets, the candidate's login (sent an invite link by email)
and an empty candidate page. Any failure leaves nothing behind. The finish screen lists the
outside services in their current mode and, once the superuser signs in, tests email, SMS and
Google sign-in from there.

The manager, comms, coordinators and mobilizers are added afterwards, from the console or the
Team page.

---

## 4. The seat, its areas and its targets

### 4.1 Geography

The reference data comes from the IEBC 2022 register (`backend/data/`), loaded once with
`campaign-crm seed`: 47 counties, 290 constituencies, 1,450 wards and 27,273 registration
centres, with each ward's and centre's registered voters and each county's 2022 turnout.

| Seat | Area | Units the team works |
|---|---|---|
| MCA | One ward | The ward's registration centres |
| MP | One constituency | Its wards |
| Women Rep, Senator, Governor | One county | Its wards |
| President | The whole country | Every ward, grouped by county |

The database holds that the seat and its area match (`models/campaign.py` `seat_matches_scope`).
Every target, mobilizer, event and contact names its unit the same way: a ward and, in an MCA
race, a registration centre.

### 4.2 Past results

`campaign-crm seed-results` loads the Kura254 historical results file
(`backend/data/history/kura254_historical_results.csv`, documented in `SOURCE.md` beside it) into
`elections`, `contests` and `contest_candidates` (`models/history.py`). It covers 2013, 2017 and
2022 for every office: President and the county seats by county, MP by constituency, MCA by ward.
A contest whose candidate votes miss its total by more than 1%, or which has no total, is
excluded; unopposed contests give no share. The load is logged with the file's checksum, so an
unchanged file is not reloaded (`--force` reloads it).

After loading, `seed-results` **reworks the targets of every open campaign**
(`services/targets.py` `recalculate_all`). A closed campaign is left as it is.

### 4.3 The seat target

The calculation is `services/win_model.py`. Every figure is an exact fraction, so a result
matches a hand calculation to the vote.

1. **Share `S`**: the 2022 winner's votes ÷ valid votes in that race.
2. **Turnout `T`**: valid votes in that same race ÷ the seat's 2022 register `R` (the sum of its
   wards).
3. **Projected valid votes `P`** = `R × (T + adjustment)`, rounded to the nearest vote, for three
   scenarios:

   | Scenario | Adjustment |
   |---|---|
   | Low | minus 3 points |
   | **Expected** (default) | none |
   | High | plus half the fall in the county's presidential turnout from August 2017 to 2022 (the whole country's for President); none if turnout rose |

4. **Seat target**: `C = ⌈P × S⌉`. The **majority line** is `F = ⌊P / 2⌋ + 1`.
   - **Two-candidate seat** (the top two took 90% or more of valid votes in 2022): the target is
     the larger of `C` and `F`, so it never falls below the majority line.
   - **Crowded seat**: the target is `C`; the majority line is shown for reference only.

**Fallbacks and reliability.** Every target carries a reliability label:

| Label | When | Share used |
|---|---|---|
| Seat data | The seat's 2022 race gives a share | The 2022 winner's share |
| Typical winner | No 2022 share (excluded, tied or unopposed) but earlier years give one | `50% + Σ w(S − 50%)` over 2013, 2017 and 2022 with weights 0.2, 0.3 and 0.5, scaled over the years present |
| Proxy | No share in any year | The national median 2022 winning share for that office |

The typical winner is also shown beside every target for reference. A seat with no usable 2022
race to judge by keeps the majority line as its floor. With no results loaded at all, the share
is one half, turnout comes from the county turnouts, and the label is Proxy; running
`seed-results` replaces these.

2017 figures come from an IEBC report that IEBC later withdrew. They feed only the typical winner
and the High scenario, and the setup preview marks the 2017 row "withdrawn data".

### 4.4 The split to wards and centres

- **Ward seats**: each ward's weight is its share of the seat's 2022 **MCA valid votes** (the only
  race with ward results). A ward with no usable MCA result takes its register at its county's
  turnout, scaled to how the other wards compare.
- **MCA seats**: each centre's weight is its share of the ward's registered voters.

`unit target = seat target × weight`, then **largest-remainder rounding**
(`win_model.share_out`): every unit takes the whole part, and the votes left over go one each to
the units with the largest fractions, so the units add up to the seat target exactly. Every unit
is asked for the same share of where the votes are, not weighted by the winner's strength there.

Targets are calculated, never typed in. `Target.votes_needed` holds the result, with the turnout
used, the scenario, the reliability and the weight. A unit's **votes committed** may be edited;
its target may not. **Refresh targets** (candidate and manager, `POST /api/targets/refresh/`)
reworks the campaign from the current register and results, adds units new since the last run,
keeps votes committed, and is audited. A register import (section 12) changes no target until
someone refreshes.

### 4.5 Worked example: Laikipia governor

`R` = 263,012. The 2022 winner took 113,783 of 167,662 valid votes: `S` = **67.86%**,
`T` = 63.75%. The top two took 96.8%, so it is a two-candidate seat. Typical winner: 59.83%.

| Scenario | Turnout | `P` | `C` | Majority line `F` | Seat target |
|---|---|---|---|---|---|
| Low | 60.75% | 159,772 | 108,429 | 79,887 | 108,429 |
| **Expected** | **63.75%** | **167,662** | **113,783** | 83,832 | **113,783** |
| High | 72.07% | 189,553 | 128,640 | 94,777 | 128,640 |

At Expected the 15 wards share 113,783 by their 2022 MCA valid votes (171,321 in all), from
Igwamiti (26,907 votes, 15.71%, target 17,870) down to Mugogodo West (4,378 votes, 2.56%,
target 2,908). `backend/tests/test_win_model.py` checks every figure here.

### 4.6 Trying and setting a scenario

The campaign holds the scenario the team works to (`Campaign.turnout_scenario`, Expected by
default, with who set it and when), and every saved target uses it. Trying a scenario and setting
one are separate steps (`services/target_scenarios.py`, `api/routers/target_scenarios.py`;
`docs/Targets_Design.md` section 6.1):

| | Trying (preview) | Setting |
|---|---|---|
| Route | `GET /api/campaigns/{id}/targets/preview/?scenario=` | `POST /api/campaigns/{id}/targets/scenario/` |
| Who | Candidate, manager and comms (`targets.preview`) | Candidate and manager only (`targets.set_scenario`) |
| What happens | The seat and every unit are worked out on the server for Low, Expected or High, beside the set targets; a President seat lists one county's wards at a time | The campaign's scenario changes and every unit's target is worked out again and saved; setting the scenario already in use is refused |
| What is saved | Nothing | The scenario, who set it and when, and every `votes_needed` |
| Record | None | An audit entry (`targets.set_scenario`) with the old and new scenario, both seat targets and the number of units changed |
| Team | Unaffected | Each coordinator whose area holds a changed unit, and each mobilizer on one, gets a notice (`GET /api/notices/`) and a call-alert push |

Mobilizers, coordinators and agents never preview. Contacts recorded never change with the
scenario; only targets and progress percentages do.

On screen, the **Targets** page (candidate, manager, comms) shows the seat target, the 2022
result behind it, the reliability badge, Low, Expected and High buttons, the majority line, the
typical winner and "Team is working to". Trying a scenario shows the banner "Previewing High
turnout. Your team is working to Expected. Nothing is saved." with each unit's change; **Use this
scenario** (candidate, manager) opens a confirmation listing the seat target change and the units
affected, with a warning when the election is less than 30 days away. Notices appear under the
bell and clear when their page is opened. A mobilizer sees a **Your ward** card with the set
target and their progress.

---

## 5. Contacts, supporters and consent

The **contact register** (`supporters` table) holds a name, a phone, a support level (Supporter,
Undecided or Opposed), the unit they are filed under, and their consent. A **supporter** is a
contact at level Supporter. One contact per phone per campaign
(`uq_supporters_campaign_phone`); Kenyan mobile numbers are stored as `+254...`.

People get on the register three ways:

| Channel | How | Consent wording recorded |
|---|---|---|
| Event QR code (`/join/<code>`) | Scans the event's code or opens its shared link; filed under the event's ward (and centre) at level Supporter | "I agree that this campaign may keep my name and phone number to contact me." |
| The campaign's sign-up link | One link per campaign for posters and groups, closed until opened; asks for the ward, or in an MCA race the centre (or Not sure) | The same |
| Added by the team | A mobilizer, coordinator, manager or the candidate enters someone met in person, after asking | "Consent to hold these details under the Data Protection Act, 2019." |

Each contact stores the channel and the exact wording the server served (`services/consent.py`),
never text from the client. The server refuses a record without consent.

The public pages give the same answer whether or not the number was already on the register, so
they never show who is registered. A device may try 20 sign-ups an hour (`api/routers/join.py`);
the count is kept in memory, per server process.

**Withdrawing.** A self sign-up gets a private link (`/withdraw/<code>`) that deletes the record.
The page answers the same for any code, and a repeat sign-up's link removes nothing. The
candidate or manager can text any contact their withdrawal link.

**What consent allows.** Bulk texts go only to contacts whose consent wording covers texts: one
that mentions SMS, text or contact. The team-entered wording does not, so those contacts are
counted as "no consent" and get no bulk texts (section 7).

---

## 6. Events, field work and the team

- **Events** (`api/routers/events.py`): schedule in a ward (and centre), record the numbers
  reached and attended, delete, open or close QR sign-ups, and invite contacts by text
  (section 7.2). A mobilizer works their own ward's events; comms reads every event.
- **Mobilizers**: one per unit (unique indexes on `mobilizers`). In an MCA race a mobilizer works
  a centre that has a target.
- **Agents**: polling agents placed at centres, moving applied, vetted, trained and ready; with
  coverage by centre and an export.
- **Assignments**: event, ward work or activity tasks for mobilizers and agents, marked done or
  cancelled; a done assignment can be paid.
- **Team sign-up link** (`/team/<code>`): mobilizers and agents register themselves, with an ID
  number; the candidate, manager or a coordinator approves or rejects. Replacing the link retires
  the old one.
- **Volunteers**: people who offer help on the website's volunteer form, each with their own
  withdrawal link; candidate, manager and coordinators manage them.
- **Team page**: the candidate adds or replaces the manager; candidate and manager add comms,
  coordinators and mobilizers, set coordinators' areas, and take people off.

---

## 7. Texts

All texting goes through `services/texting.py`: one `sms_log` row per number, and delivery
reports and STOP replies come back to it. Every text ends with "Reply STOP to opt out." Numbers
that replied STOP, or that the gateway reported as opted out, are never texted again.

### 7.1 Bulk texts through the compliance queue

A text to many contacts is a **run** (`sms_runs`, one row per number in `sms_outbox`), built and
sent by `services/sms_queue.py`.

1. The candidate, manager, comms or a coordinator (for their area) **drafts** a message for some
   or all wards (`POST /api/messages/`).
2. The candidate or manager **approves** it and confirms its language
   (`POST /api/messages/{id}/send/`). Approval runs the gate:

   | Check | Refused or held when |
   |---|---|
   | Candidate's name | The text does not contain the candidate's name as registered |
   | Language | Not English (`en`) or Kiswahili (`sw`) |
   | Consent | Nobody in the audience consented in a wording that covers texts |
   | Opt-outs | Opted-out numbers are left out and counted |
   | Campaign period | Today is past `CAMPAIGN_PERIOD_END` |
   | Vetting | With `SMS_VETTING_REQUIRED=true`, the run waits as `awaiting_vetting` until a vetting reference is entered |

   The run records how many were targeted, left out for no consent and left out as opted out,
   the parts per text, and an estimated cost (`SMS_PART_PRICE_CENTS` a part, default KES 0.80).
3. **Window.** Texts go only inside `SMS_WINDOW` (default and widest 08:00 to 18:00, Nairobi
   time) and inside the campaign period when one is set. Outside it the run waits as
   `scheduled` and shows when it can next go.
4. **Batches.** A batch is up to `SMS_BATCH_SIZE` numbers (at most 500, one gateway request).
   The first batch goes at approval when the window is open. Later batches go when the queue is
   drained: `POST` (or `GET`, for a scheduler) `/api/internal/sms/drain/` with
   `Authorization: Bearer $CRON_SECRET`, or `campaign-crm sms-worker`, which drains every 30
   seconds. No scheduler is wired in `vercel.json`.
5. **Before every batch** the gate runs again, and each number is checked again for consent,
   withdrawal, erasure and opt-out; a number that fails is skipped with the reason.
6. **Idempotency.** A batch is claimed with a conditional update, so two workers never take the
   same number. Each batch keeps one idempotency key across retries, so a gateway that took it
   and lost its answer sees a repeat, not a second text. Rows left `sending` by a worker that
   died are sent again after 15 minutes under the same key. A gateway refusal (4xx) fails the
   batch for good; other failures retry with a growing delay, up to `SMS_MAX_ATTEMPTS`.
7. **Pause, Resume, Halt** (candidate and manager). Pause holds the run and Resume picks it up.
   Halt needs a reason, skips everything still queued and cannot be undone. A batch already with
   the gateway still lands.
8. **Consent evidence.** `GET /api/campaigns/{id}/sms-runs/{run_id}/consent.csv` lists each
   number with its name, status, when consent was recorded, the channel and the wording.

The Bulk sends screen shows each run's stage, counts, delivered count, estimated and actual cost,
and these actions. Every approval, pause, resume, halt and vetting is audited.

### 7.2 Event invitations

`POST /api/events/{id}/invite/` goes through the same queue: the same name and language check,
consent filter, window, batches and run screen. A preview (`dry_run`) sends nothing, is open to
anyone who may change the event, and shows who would be texted. Sending needs the candidate or
the manager. Invitations go to the event's ward or the whole campaign, filtered by support level,
inside the caller's reach. The event's number reached follows how many texts the run sent.

### 7.3 The test SMS

Messages has **Send test SMS** (`POST /api/console/sms/test/`, candidate and manager): one text,
sent at once past the queue, logged and audited, with a status column (Sent, Delivered, Failed)
that refreshes while any row is not final. With a live gateway it only texts a login of the
campaign or a consenting contact. The SMS test in setup and in the console is separate: with
Sozuri it calls Sozuri's auth test and sends nothing.

### 7.4 Gateways and practice mode

`SMS_PROVIDER` picks the gateway (`services/sms.py`):

| Provider | What it does |
|---|---|
| `console` (default) | Practice mode: logs each text, sends nothing, costs nothing |
| `sozuri` | Sozuri's API. Needs `SOZURI_PROJECT`, `SOZURI_SENDER_ID` and `SOZURI_API_KEY`, or the app refuses to start. Sozuri has no sandbox, so testing uses a separate Sozuri test project with its own key; any real key sends real texts |
| `africastalking` | Africa's Talking. Needs `AT_USERNAME` and `AT_API_KEY`; the username `sandbox` uses their test gateway |

Delivery reports and inbound texts come back to URLs carrying `SMS_CALLBACK_SECRET`
(`api/routers/sms_callbacks.py`); a wrong secret gets 404. A Sozuri callback must also carry a
valid `X-Sozuri-Signature` (HMAC-SHA256 over the timestamp and the raw body, keyed with
`SOZURI_SIGNING_SECRET`, at most 300 seconds old) or it gets 401; when `SOZURI_AUTH_KEY` is set,
the body's auth key must match too. A report is applied once and repeats are ignored. Telkom
numbers (`+25477...`) get no Sozuri delivery report, so they stay Sent.

---

## 8. Online calls and call alerts

**Calls** run on LiveKit (`services/meetings.py`, `frontend/src/pages/Meet.jsx`, and the Calls
page under Reach out).

- The candidate, manager, comms, or a coordinator (for a ward of theirs) starts an audio or video
  call for the whole campaign or one ward. A ward call rings the candidate, manager and comms,
  the coordinators whose area holds the ward, and its mobilizers.
- Any login of the campaign joins at `/meet/<id>` with a 15-minute token for that room only. An
  audio call allows the microphone alone.
- The host, the candidate or the manager ends a call for everyone.
- LiveKit's signed webhook (`POST /api/livekit/webhook/`) records joins, leaves and room end; the
  Calls list shows past calls with who came and for how long.
- With no `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`, starting a call is refused
  with "Meetings are not configured".

**Call alerts** are web push (`services/push.py`). The frontend is a PWA (`vite-plugin-pwa`,
service worker `frontend/src/sw.js`) whose service worker caches nothing and only shows
notifications. After sign-in the app offers "Enable call alerts"; on an iPhone they work once the
app is added to the Home Screen (iOS 16.4 or later). Starting a call notifies the people it
rings ("Joining: title"); tapping the alert opens the call. Only https endpoints of the browsers'
push services (Google, Mozilla, Apple, Microsoft) are accepted, a subscription the push service
reports gone is deleted, and signing out unsubscribes the device. With no VAPID keys set nothing
is sent; `campaign-crm make-vapid-keys` prints a key pair.

---

## 9. Payments and payouts

**Payouts** pay mobilizers (for an event or a done assignment) and agents
(`api/routers/payments.py`, `services/payout_flow.py`).

- A coordinator (for their area) or the manager schedules a payment. Whoever schedules never
  approves it: a coordinator's goes to the manager, a manager's to the candidate
  (`services/payment_routing.py`). The candidate never schedules.
- The approver releases it, declines it, or marks it paid by hand with a reference.
- A payment moves scheduled, sending, paid, failed or cancelled. Each move is one conditional
  update, so two requests cannot move the same payment. One live payment per mobilizer per event,
  and one per assignment.
- `PAYOUT_PROVIDER=practice` (default) moves no money and marks each release paid under a
  `PRACTICE` reference. `paystack` sends M-Pesa transfers from the Paystack balance, checks the
  balance first, and settles from Paystack's signed webhook at `/api/payments/paystack/webhook/`.
- The Payments page compares the ledger with Paystack on request. A long-running server also does
  it every `RECONCILE_HOURS` (0 turns it off).

**Contributions** come in from the website's Contribute page (`services/payments_in.py`): an
M-Pesa prompt on the payer's phone through Paystack (`PAYIN_PROVIDER=paystack`; practice mode
marks it paid at once and takes nothing), or the payer's own Paybill or Till payment, which the
candidate or manager confirms or rejects from its M-Pesa code.

---

## 10. The public website

The candidate's site is at `/`, in the installation's name, logo and colours: Home, About,
Agenda (each issue at `/issues/<id>`), Media (videos and documents), News (each post at
`/news/<id>`), Events, Volunteer, Contribute, Privacy (the privacy notice from setup), and Sign in
at `/signin`. Other public pages: `/join/<code>`, `/withdraw/<code>`, `/team/<code>`,
`/volunteer/withdraw/<code>`, `/unsubscribe/<code>`, `/invite/<token>`, `/reset/<token>` and
`/forgot-password`.

The candidate, manager and comms edit it from the workspace's Website and Settings pages
(`api/routers/workspace_site.py`): the candidate profile, posts, slides, issues, documents,
videos and site settings, with uploaded images. Public routes return published rows only. The
footer's news sign-up stores its consent wording and is undone at `/unsubscribe/<code>`.

---

## 11. Privacy

Built for the Data Protection Act 2019 (`services/privacy.py`, and the Personal data page for
the candidate and manager):

- **Data requests**: access, correction or erasure, logged with a due date of 7, 14 and 14 days
  (Data Protection (General) Regulations 2021), and marked answered with who and when.
- **Erasure**: blank one contact, a withdrawn volunteer, or the sign-up (ID number included) of a
  mobilizer or agent who has left. Counts stay; the person's details go, including their number
  on past texts and in runs not yet sent.
- **Withdrawal links**: self sign-ups keep their own, and the team can text one to any contact.
- **Closing**: after the election the candidate closes the campaign. It is read-only for good,
  except sign-out and the data protection work. After the retention period (6 months by
  default, adjustable) every contact can be erased in one step.
- **Audit**: sensitive actions are recorded with who, what and when; the superuser reads the
  trail in the console.

---

## 12. The console and imports

The superuser's console at `/console` (`frontend/src/components/Admin.jsx`,
`api/routers/admin.py`):

| Section | What it does |
|---|---|
| Campaigns | The campaign with its people; rename, add or remove members, delete |
| Logins | Create logins (each gets an invite link by email), reset passwords, turn logins off and on, change emails |
| Settings | The site's name, logo, colours, contacts and privacy notice |
| Areas and register | Boundary and voter register imports from CSV, with a dry run and the import history |
| Health | Version, migration, database, outside services, last backup and disk space |
| Audit | The audit trail |
| Export | Every table as JSON and CSV in one zip, password hashes left out |

The console also sends a test SMS and a test payout.

**Imports** (`services/imports.py`) check every row before writing anything; one bad row and the
file changes nothing. Areas match by code. An area left out of a boundary file is retired: hidden
from pickers, kept for everything that refers to it. A register import sets registered voters per
county, ward and centre, and turnout per county.

The command line `campaign-crm` (`cli.py`) runs the same services: `seed`, `seed-results`,
`setup-token`, `createuser`, `users`, `campaign`, `reset-password`, `set-email`, `activate`,
`deactivate`, `add-member`, `remove-member`, `rename-campaign`, `delete-campaign`,
`import-boundaries`, `import-register`, `export`, `backup`, `restore`, `reset-database`,
`sms-worker`, `make-vapid-keys`, and the demo commands `demo`, `demo-install` and `demo-comms`.

---

## 13. Architecture

| Part | Stack | Where |
|---|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy 2.0 async, Pydantic v2, Alembic, uv | `backend/` |
| Frontend | React 19 SPA: Vite, React Router, TanStack Query, Zustand, Tailwind CSS v4 UI kit, LiveKit components, a PWA service worker | `frontend/` |
| Contract | The fields the frontend reads and sends | `contracts/frontend-api.json` |
| Database | Postgres: a local one in development, Neon for the demo installs | |

**The API** is about 200 operations, all under `/api`, plus `/health`
(`api/routers/__init__.py`). The interactive list is at `/docs` only with `DEBUG=true`.

**How a request is scoped.** The `Authorization: Token <key>` header names the caller
(`api/deps.py`). `require("<action>")` checks the role against `MAP`, and `api/scope.py` limits
reads and writes to the caller's campaign and reach. A campaign the caller is not on answers 404.
Unique indexes hold the rules (one candidate, one manager, one mobilizer per unit, one contact per
phone) even when two requests race.

**The contract.** `contracts/frontend-api.json` lists every field the SPA reads and sends.
`backend/evals/test_frontend_contract.py` checks the API still offers them, and
`frontend/tests/contract.test.js` checks the frontend still matches, so renaming a field on one
side fails both until the other follows.

**Outside services** each sit behind a small interface with a safe default, so an installation
runs in full with no keys: email (`practice` logs each email), SMS (`console`), payouts and
contributions (`practice`), calls (off), call alerts (off) and Google sign-in (off). The services
panel in setup and the console's Health section show each one's mode.

**Checks.** `cd backend && uv run pytest` runs the tests and evals with no database server
(`TEST_POSTGRES=1` runs them on a throwaway local Postgres); `cd frontend && npm test` runs the
frontend tests; `tools/secret-scan/scan.py` runs as a pre-commit hook and on every push.

---

## 14. Deployment

Two ways to run an installation; `DEPLOY.md` has the steps.

- **Vercel and Neon** (the demo installs, `docs/Demo.md`). `vercel.json` defines two services in
  one project, region `fra1`: `web` (the Vite app in `frontend/`, deep paths fall back to
  `index.html`) and `api` (the FastAPI app from `backend/asgi.py`). `/api/*` and `/health` go to
  `api` and everything else to `web`, so the site and the API share one address. The database is
  Neon Postgres in Frankfurt. `tools/deploy-demo.sh` creates, configures and deploys a project.
  Migrations and data loads run from a developer's machine against the Neon database. Uploaded
  files are not kept, and nothing runs in the background, so later SMS batches need a drain call.
- **One server with Docker** (`deploy/`): `docker-compose.yml` runs Postgres 17, a one-off
  `migrate` step, the app (the `Dockerfile` image: the built SPA and the API on one origin), a
  nightly backup and Caddy for HTTPS.
