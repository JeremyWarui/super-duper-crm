# Communications Design: rooms, meetings and calls (Release 6)

| | |
|---|---|
| Document ID | `CD-R6` |
| Version | 0.5, 24 November 2026 |
| Status | **Draft, awaiting approval** |
| Mockups | [`design/R6_Mockups.html`](design/R6_Mockups.html): `M1` Console meeting, `M2` Field app |
| Demo slice | [`Comms_Demo_Plan.md`](Comms_Demo_Plan.md) (`DM-R6`): SMS queue, online meetings, PWA and push |
| Applies to | Every installation: one candidate contesting one seat |
| Release | 6 (tickets `R6-0` to `R6-7` and `R6-9`) |

How to use this document: every ticket in section 12 names the decisions (`D`), sections and
mockups (`M`) it implements. A ticket is done when its "Done when" line holds and its row in the
tracker (section 15) is ticked. Changes to an approved version get a new amendment (`A`) entry in
section 16 and a version bump.

---

## 1. Purpose

MZIGO CRM grows from a campaign records system into a campaign records **and** team communication
platform. This document records what is kept, changed, removed and added.

### Decisions for approval

| ID | Decision | Approved |
|---|---|---|
| D1 | One installation type: one candidate contesting one seat (A2). | [ ] |
| D2 | The frontend is split into a **Console** (desktop, decision-makers) and a **Field app** (installable phone app, people on the ground), both in the existing React project. | [ ] |
| D3 | A communication module adds rooms, meetings and calls, scoped to the campaign space. | [ ] |
| D4 | All calls go from the platform to people. No inbound numbers, call-in conferences or missed-call callbacks. | [ ] |
| D5 | ~~SMS stays in the code but is dormant.~~ **Replaced by D9 (A3).** | [ ] |
| D6 | LiveKit provides calls: localhost in development, LiveKit Cloud for the pilot, a Kenyan VPS for production phone calls. The CRM stays on Vercel. | [ ] |
| D7 | Every call to a supporter is drafted and approved, under the same rule as texts today. | [ ] |
| D8 | Missed phone participants are retried automatically and can be rung again by the host (amendment A1). | [ ] |
| D9 | Bulk SMS is sent through an outsourced, licensed bulk SMS provider, and only through the platform's compliance queue (section 5.5, amendment A3). The platform never sends a bulk text directly from a request. | [ ] |
| D10 | Calls and SMS share one queue service: Vercel Queues on the hosted deployment, a worker process on self-host. | [ ] |
| D11 | Providers (A4): Sozuri for bulk SMS; LiveKit for meetings (LiveKit Cloud for the pilot, an Angani server in Nairobi for production); SautiKit for calls to basic phones, through SIP if offered, otherwise its audio stream and a bridge service. WhatsApp is out of scope (Meta's policy prohibits political campaigns). | [ ] |

---

## 2. The CRM today

### 2.1 What it is

The CRM gives a Kenyan campaign one number to chase, the **seat target** (the share the last
winner took, applied to the votes expected), broken down by ward (MP, Governor, Senator, Women Rep,
President) or by registration centre (MCA), on the real 2022 register. The team records
mobilizers, events and supporters, and the strategy read shows where the campaign stands and where
to go next. Each installation also runs the candidate's public website.

### 2.2 Who uses it

Operator (superuser); candidate; campaign manager; coordinator; comms; mobilizer; agent; and
supporters, who have no login.

### 2.3 Architecture today

```
Browser: React 19 SPA (Vite, TanStack Query, Zustand, react-router)
        │  JSON + token
        ▼
Vercel (fra1): service "web" = built SPA, service "api" = FastAPI (asgi:app)
        │
        ├── Neon Postgres (SQLAlchemy 2.0 async, Alembic)
        ├── SMS provider: console (Africa's Talking written, never live)
        └── Payout provider: practice (Paystack written, never live)

Self-host package: Docker Compose (Postgres, app, Caddy, nightly backup)
```

Strengths to protect: every rule is enforced on the server; `services/permissions.py` (reach: all,
area, own) and `api/scope.py` (campaign, area, ward) gate every request; database unique indexes
back up the rules; outside services default to practice mode; the contract file is checked by both
test suites.

### 2.4 Current workspace screens (aspirant demo, 19 November 2026)

| Group | Pages |
|---|---|
| Plan | Overview, Strategy, Targets, Wards |
| Field | Events, Mobilizers, Agents, Assignments, Contacts, Volunteers |
| Reach out | Messages (SMS composer, practice mode) |
| People | Team, Sign-ups, Personal data |
| Money | Payments, Contributions |
| Site | Website, Settings |

Top bar: breadcrumb, search, Area picker, notifications, help, signed-in person. Style: warm
off-white page, white cards, navy primary buttons, yellow win-number accent. New screens keep it.

### 2.5 Known limits relevant to this release

1. Field screens are not designed for a phone (known gap 5, planning question 3).
2. `main.py` runs an endless background loop (`_reconcile_daily`) that does not run reliably on
   Vercel Functions.
3. Uploads are written to local disk (`backend/uploads`), which does not persist on Vercel.
4. Team communication happens outside the system, typically in WhatsApp groups.

---

## 3. The CRM at the end of Release 6

### 3.1 What it becomes

The same campaign records system, plus a place where the team talks, meets and is recognised.
Coordinators and mobilizers join ward rooms, attend audio or video meetings, and take part even
from a basic phone, because the platform rings them into the same meeting. Feedback from the field
is tracked to a visible outcome.

### 3.2 Target architecture

```
Console (desktop)          Field app (installable PWA, phone-first)
            \                  /
             React 19 SPA, one project, two layouts
                       │  JSON + token, LiveKit token
                       ▼
Vercel (fra1)
  web: SPA, service worker, offline storage (Dexie)
  api: FastAPI
       ├─ existing modules (unchanged rules)
       ├─ rooms, meetings, calls, feedback (new)
       ├─ LiveKit webhooks (signature checked)
       ├─ Vercel Queue handlers (call retries)
       └─ cron routes (reminders, reconciliation, SMS queue)
                       │
     ┌─────────────────┼──────────────────────┬───────────────────┐
     ▼                 ▼                      ▼                   ▼
Neon Postgres    LiveKit (Cloud, then      SIP trunk provider   Vercel Blob
(new tables)     Kenyan VPS: server,       (outbound only)      (photos, voice
                 SIP, Redis)                    │                notes, uploads)
                       ▲                        ▼
       browsers join over WebRTC        ordinary phones joined into the same room
```

Control and media are separate. FastAPI decides who may call whom and records everything. LiveKit
only carries the audio and video.

---

## 4. Keep, change, remove, add

### 4.1 Kept as they are

| Area | Notes |
|---|---|
| Win number, targets, strategy read | Unchanged; computed, never stored |
| Geography (counties to registration centres) | Unchanged; also defines ward rooms |
| Roles, `permissions.py`, `scope.py` | Unchanged; extended with new actions (section 7) |
| One login, one campaign | Unchanged |
| Supporters, consent recording, withdrawal links | Unchanged; consent wording extended (section 9) |
| Mobilizers, agents, team sign-up, approvals | Unchanged |
| Events, QR sign-up, campaign sign-up link | Unchanged |
| Payments, payouts, subscription ledger, audit | Unchanged; the ledger pattern is reused for call costs |
| Practice mode for outside services | Unchanged; telephony gets a practice provider too |
| Contract file and both test suites | Unchanged; each ticket updates them |
| Self-host Docker Compose package | Kept and extended with LiveKit services |

### 4.2 Changed

| Area | Today | After Release 6 |
|---|---|---|
| Frontend shell | One layout for every role | Console for candidate, manager and comms; Field app for coordinators, mobilizers, agents and volunteers (`M1`, `M2`) |
| Field screens | Desktop tables and forms | Phone-first, installable, offline-capable |
| Sidebar "Reach out" | Messages only | **Comms**: Rooms, Meetings, Messages (dormant); plus **Feedback** (`M1`) |
| Event cards | Record, Invite, Sign-up QR, Assign | Adds **Start meeting** |
| Event invitations | By SMS (dormant) | In-app notification, or a platform call to consenting people |
| Notifications | Counts in the top bar | In-app inbox for every login, plus web push |
| Background jobs | Endless loops in `main.py` | Vercel Cron routes and Queue handlers calling the same services |
| File storage | Local disk | Vercel Blob (or S3-compatible) behind one storage interface; local disk in development and self-host |
| Consent wording | Holding data (and texts) | New version also covers phone calls |
| Planning question 9 | Consent confirmed by SMS YES/STOP | Consent confirmed by a call: press 1 to confirm, 2 to withdraw |
| `docs/SYSTEM.md` section 7 | Describes Fly.io | Describes Vercel, LiveKit and Blob |

### 4.3 Removed or retired

| Item | Treatment |
|---|---|
| `fly.toml` and Fly.io references | Removed once Vercel is confirmed as the only hosted target |
| Direct SMS sending from the approval request | Replaced by the compliance queue (A3). `SMS_PROVIDER=console` stays the practice default |
| "Messages" as a main sidebar group | Moved under Comms, marked dormant |
| Endless `asyncio` loops in `lifespan` | Removed from the hosted deployment; self-host keeps an optional loop |

Nothing that holds data is deleted.

### 4.4 Added

| Feature | Summary | Mockup |
|---|---|---|
| Spaces | Campaign space | |
| Rooms | Campaign-wide, ward, role group, custom; topics, posts, photos, voice notes | `M2` Room |
| Announcements | Room posts by approved roles; draft and approve where required | `M2` Room |
| Meetings | Scheduled or instant; audio first, video optional; host controls | `M1`, `M2` Meeting |
| One-to-one calls | App to app, or the platform rings an ordinary phone | |
| Phone bridge | Basic phones dialled into the same meeting; press 1 to raise a hand | `M1` |
| Missed-call retry and Ring again | Amendment A1 | `M1` |
| "Call my phone instead" | An app user with no data is rung into the meeting | `M2` Home, Meeting |
| Post-meeting keypad feedback | Press 1, 2 or 3 | |
| Feedback tracking ("You said, we did") | Submitted, acknowledged, under review, action taken, outcome | `M1` sidebar, `M2` Home |
| Field journal | Offline notes and reports, synced when connected | `M2` Record tab |
| Contact preferences | Quiet hours, call limits, language, opt-out | `M2` Me tab |
| Call costs | Per-leg seconds and cost, budgets | `M1` |
| Bulk SMS compliance queue | Runs, batches, sending window, consent and opt-out checks, vetting reference, halt, consent evidence export (A3) | `M1` |

---

## 5. Communication model

### 5.1 Spaces

| Space | Contains | Members | Visible to |
|---|---|---|---|
| Campaign space | Campaign rooms, meetings, calls | That campaign's logins and consented phone contacts | That campaign only |

### 5.2 Room membership is derived

A mobilizer belongs to their ward's room; a coordinator to the rooms of their area; the candidate
and manager to every room in their campaign. Only custom rooms store member rows. Moving a
mobilizer to another ward moves them to that ward's room.

### 5.3 Participants without a login

A `Mobilizer` with no login, a consented `Supporter`, or a consented campaign volunteer can
be rung into a meeting. They never get an account; the call records them as a phone participant.

### 5.4 Call flows

**Meeting with mixed participants (`M1`)**

1. The host opens a meeting and presses Start.
2. The API checks permission, consent, quiet hours, call limits and budget for each invitee.
3. App users get a push notification and join in the browser.
4. For each phone invitee, the API asks LiveKit to dial out through the SIP trunk.
5. Phone participants join audio-only and press 1 to raise a hand.
   - 5a. **Automatic retry.** An unanswered, busy or unreachable phone participant is rung again
     after 2 minutes, up to 2 more times (3 attempts). Retries stop when they join, when the
     meeting ends, or if they press 9 to opt out.
   - 5b. **Ring again.** The host's participant list shows Ringing, Joined, Retrying (attempt n of
     3), No answer or Left. Anyone not in the meeting has a Ring again button that places one
     immediate call, also after automatic retries are used up, while the meeting is live.
6. LiveKit webhooks report joins and leaves; the API records each `CallLeg` with seconds and cost.
7. Optionally, at the end, phone participants receive a keypad feedback call.

**One-to-one call.** The caller picks a person. Online in the app: an app call. Otherwise the
platform rings their phone. Both are recorded as a `CallSession` with legs.

---

### 5.5 Bulk SMS through the compliance queue (amendment A3)

The platform does not operate its own SMS gateway. Bulk texts are handed to an outsourced bulk
SMS provider that is licensed as a content service provider and has interconnection with the
mobile networks (`SMSProvider` interface; Africa's Talking is already built). The provider
registers the sender ID with each network and passes political content to the networks for
vetting. The platform's job is to make sure nothing reaches the provider that breaks the rules,
and to send at a pace that suits both the provider and the rules.

**A run's life**

| Stage | What happens |
|---|---|
| Draft | A comms login drafts the message and picks wards (as today) |
| Approve | The candidate or manager approves (as today); approval creates an `sms_runs` row instead of sending |
| Compliance gate | The checks below run; a failure refuses the run with the reason |
| Vetting | Where the provider requires it, the verbatim text, the candidate's authorisation letter and the intended timing go to the provider at least 48 hours before sending; the run waits in `awaiting_vetting` until the provider's reference is recorded |
| Scheduled | The run waits for its start time, inside the sending window and the campaign period |
| Sending | The queue worker sends one batch at a time; checks repeat before each batch |
| Receipts | Delivery reports update each `sms_outbox` row (existing callback route) |
| Completed or halted | Totals and actual cost are fixed; the consent evidence file stays downloadable |

**Compliance gate** (checked at approval and again before every batch)

| Check | Rule it serves |
|---|---|
| The text names the candidate as registered on the campaign | Political messages must bear the name of the party or individual sending them |
| Language declared as English or Kiswahili, confirmed by the approver | Political bulk messages in English or Kiswahili only |
| Recipients are supporters with recorded consent whose consent wording covers SMS | No unsolicited political messages; Data Protection Act consent for direct marketing |
| Numbers on `sms_opt_outs` (campaign or installation-wide) are skipped, including opt-outs received during the run | Opt-out must work at all times |
| An opt-out line ("Reply STOP to stop") is added automatically and counted in the length | Consumer protection guidelines: marketing SMS carry an opt-out |
| Sending only between 08:00 and 18:00 East Africa Time; the setting may narrow this window but never widen it | Political guidelines allow 08:00 to 18:00; consumer guidelines 07:00 to 19:00; the stricter applies |
| Sending only within the campaign period set for the installation | Political messaging must respect the campaign period |
| Estimated cost within the communication budget | Budget rule (rule 5) |
| Vetting reference recorded when the provider requires one | Network vetting before political content is sent |

**Halt.** The candidate or manager can halt a run at any time; the next batch does not go. If a
network or the provider stops a run, the run is marked halted with the reason. An apology or
correction message, when needed, is a new run and passes the same gate.

**Consent evidence.** For any run, a CSV lists each recipient with consent date, channel and
wording version, so the campaign can answer a request from the provider, a network or the
regulator immediately.

**The worker**

- Each batch is one queue message (Vercel Queues on the hosted deployment; a worker process on
  self-host). A scheduled sweep picks up any batch left stuck.
- Batch size and rate come from settings and the provider's limits.
- `sms_outbox` has a unique (run_id, phone) key. A number accepted by the provider is never sent
  again; only transient provider errors are retried, with growing delays, up to `SMS_MAX_ATTEMPTS`.
- A batch that would run past 18:00 stops at the window edge and resumes at 08:00 the next day,
  inside the campaign period.
- Every run and halt is written to the audit trail.

**Console screen (`M1` Comms):** each run with its stage, counts (targeted, excluded for no
consent, excluded for opt-out, sent, delivered, failed), cost, and Pause, Resume and Halt.

---

## 6. Data model additions

Every table carries `campaign_id`.

| Table | Key fields | Notes |
|---|---|---|
| `rooms` | id, campaign_id, kind (campaign, ward, role, custom), ward_id, county_id, role, title, archived | Ward and role rooms unique per campaign |
| `room_members` | room_id, user_id | Custom rooms only |
| `room_topics` | room_id, title, pinned | |
| `room_posts` | topic_id, author_id, body, kind (post, announcement), media, status | |
| `meetings` | space, title, host_id, room_id, event_id, mode (audio, video), scheduled_at, status, livekit_room, auto_retry (default on), retry_attempts (default 2), retry_delay_seconds (default 120) | |
| `meeting_invites` | meeting_id, user_id or phone contact ref, channel (app, phone), status (pending, ringing, joined, retrying, no_answer, left), attempts_used, host_redials, next_retry_at | |
| `call_sessions` | space, kind (meeting, direct, feedback, consent_check), started_by_id, approved_by_id, started_at, ended_at | |
| `call_legs` | session_id, participant ref, channel, phone, provider_ref, attempt, trigger (start, auto_retry, host_redial), outcome (answered, no_answer, busy, failed, opted_out), joined_at, left_at, seconds, cost_cents | One per attempt |
| `call_opt_outs` | phone, campaign_id or null | Mirrors `sms_opt_outs` |
| `contact_preferences` | phone or user_id, quiet_from, quiet_to, max_calls_per_week, language | |
| `call_spend_entries` | campaign_id, session_id, amount_cents, kind (charge, budget, adjustment) | Ledger pattern |
| `feedback_items` | space, ward_id, author ref, channel (app, keypad), body or keypress, status | |
| `feedback_status_changes` | item_id, status, note, by_id, at | |
| `journal_entries` | campaign_id, author_id, ward_id, body, media, client_id, synced_at | `client_id` makes offline sync idempotent |
| `push_subscriptions` | user_id, endpoint, keys | |
| `sms_runs` | campaign_id, message_id, status (awaiting_vetting, scheduled, sending, paused, halted, completed), language, sender_name, vetting_ref, vetted_at, scheduled_for, targeted, excluded_no_consent, excluded_opted_out, sent, delivered, failed, segments, estimated_cost_cents, actual_cost_cents, approved_by_id, halted_by_id, halt_reason | One per approved bulk message (A3) |
| `sms_outbox` | run_id, supporter_id, phone, status (queued, sending, sent, delivered, failed, skipped), skip_reason, attempts, next_attempt_at, sms_log_id, sent_at | Unique (run_id, phone): a retry can never text the same person twice |

---

## 7. Permission additions (`services/permissions.py` `MAP`)

| Action | Candidate | Manager | Coordinator | Comms | Mobilizer | Agent |
|---|---|---|---|---|---|---|
| `rooms.read` | all | all | area | all | own | own |
| `rooms.post` | all | all | area | all | own | own |
| `rooms.announce` | all | all | area | all | no | no |
| `rooms.announce.approve` | all | all | no | no | no | no |
| `rooms.moderate` | all | all | area | no | no | no |
| `meetings.read` | all | all | area | all | own | own |
| `meetings.host` (includes Ring again) | all | all | area | no | no | no |
| `calls.direct` | all | all | area | no | no | no |
| `calls.supporters` | all | all | area | all | no | no |
| `calls.supporters.approve` | all | all | no | no | no | no |
| `feedback.submit` | all | all | area | all | own | own |
| `feedback.respond` | all | all | no | no | no | no |
| `calls.budget` | all | all | no | no | no | no |

---

## 8. Layouts

### 8.1 Aspirant Console (candidate, manager, comms): `M1`

| Section | Contents | Status |
|---|---|---|
| Plan | Overview (adds a Today strip), Strategy, Targets, Wards | Kept |
| Field | Events (adds Start meeting), Mobilizers, Agents, Assignments, Contacts, Volunteers | Kept |
| Comms | Rooms, Meetings, Messages (dormant) | New |
| Feedback | You said, we did | New |
| People | Team, Sign-ups, Personal data (adds call consent and opt-outs) | Kept |
| Money | Payments, Contributions, call spend and budget | Kept |
| Site | Website, Settings (adds calling hours and retry options) | Kept |

### 8.2 Aspirant Field app (coordinator, mobilizer, agent): `M2`

| Tab | Contents |
|---|---|
| Home | Next meeting (Join, Call my phone), room activity, my tasks, feedback status |
| Room | Ward or team room: announcements, topics, posts, photos, voice notes |
| Meetings | Join in the app, raise hand, Call my phone, leave |
| Record | Event, supporter, journal entry (offline) |
| Me | Assignments, payments, contact preferences |

---

## 9. Rules

1. **Consent before any call.** A new consent wording version in `services/consent.py` covers
   phone calls. People registered under the old wording are not called until they confirm.
2. **Opt-out on every call.** Pressing 9 writes a `call_opt_outs` row.
3. **Quiet hours and limits.** Every dial-out checks contact preferences and the calling window.
4. **Political content.** Calls to supporters name the candidate and use English or
   Kiswahili; both are required on the approval step.
5. **Budgets.** A meeting cannot start dialling if the estimated cost exceeds the remaining budget.
6. **Audit.** Scheduling, approval, every dial-out and every opt-out is written to the audit trail.
7. Withdrawn (A2).
8. **Recordings off by default.** Only with host choice and an announcement to every participant.
9. Withdrawn (A5).
10. **Retries respect every rule.** Each retry and re-dial is checked again against consent,
    opt-out, quiet hours and budget. Retries do not count toward the weekly call limit; host
    re-dials do. At most 3 re-dials per person per meeting.
11. **Bulk SMS only through the queue.** Every bulk text passes the compliance gate in 5.5 at
    approval and again before each batch. A run that fails a check waits or stops with a reason;
    nothing is sent around it.

---

## 10. Infrastructure and settings

| Stage | Calls | Hosting |
|---|---|---|
| Development | LiveKit on localhost (`livekit-server --dev` or Docker), `TELEPHONY_PROVIDER=console` | Local FastAPI and Vite |
| Pilot | LiveKit Cloud, SIP trunk that accepts connections from abroad | CRM on Vercel |
| Production | Kenyan VPS: LiveKit server, LiveKit SIP, Redis | CRM on Vercel; Blob for files |
| Self-host | LiveKit services added to `deploy/docker-compose.yml` | Buyer's server |

LiveKit cannot be hosted on Vercel, Netlify or Render (no inbound UDP). Railway runs it TCP-only and
cannot run LiveKit SIP.

**Call retries on Vercel.** The LiveKit webhook reports an unanswered phone participant; the API
records it and schedules a delayed Vercel Queue message (120 seconds); the handler checks the
meeting is still live and the person has not joined, then dials. Fallback: the host's open meeting
screen asks every 30 seconds for retries that are due.

**Settings (practice-safe defaults)**

- `LIVEKIT_URL` and `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`
- `TELEPHONY_PROVIDER=console` (or `livekit_sip`), `SIP_TRUNK_ID`, `CALLER_NUMBER`
- `CALL_WINDOW=08:00-19:00`, `CALL_COST_PER_SECOND_CENTS`
- `CALL_RETRY_ATTEMPTS=2`, `CALL_RETRY_DELAY_SECONDS=120`, `CALL_MAX_HOST_REDIALS=3`
- `STORAGE_PROVIDER=local` (or `blob`), `BLOB_READ_WRITE_TOKEN`
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`
- `CRON_SECRET`
- `SMS_PROVIDER=console` (or the contracted provider), `SMS_SENDER_ID`, `SMS_WINDOW=08:00-18:00`,
  `SMS_BATCH_SIZE=500`, `SMS_RATE_PER_MINUTE`, `SMS_MAX_ATTEMPTS=3`, `SMS_VETTING_LEAD_HOURS=48`,
  `SMS_COST_PER_SEGMENT_CENTS`, `CAMPAIGN_PERIOD_START`, `CAMPAIGN_PERIOD_END`

**Packages.** Backend: `livekit-api`, `pywebpush`. Frontend: `livekit-client`,
`@livekit/components-react`, `vite-plugin-pwa`, `dexie`.

---

## 11. Features: now compared with the end of Release 6

| Capability | Now | End of Release 6 |
|---|---|---|
| Seat target, targets, strategy | Yes | Yes |
| Mobilizers, agents, events, supporters | Yes | Yes |
| Payments and payouts (practice) | Yes | Yes |
| Website, dashboard | Yes | Yes |
| SMS texts and invitations | Built, sent in one request | Sent through the compliance queue (A3) |
| Phone-first field screens | No | Field app, installable |
| Offline capture | No | Journal; supporters later |
| Team rooms | No | Yes |
| Announcements with approval | Texts only | In rooms |
| Audio and video meetings | No | Yes |
| Basic phones in meetings | No | Phone bridge, keypad hand-raise |
| Missed-call retry and Ring again | No | Yes |
| One-to-one calls | No | App or phone |
| Post-meeting keypad feedback | No | Yes |
| Feedback tracked to an outcome | No | You said, we did |
| In-app inbox and web push | Top-bar counts only | Every login |
| Call consent, opt-out, quiet hours | No | Yes |
| Call costs and budgets | No | Yes |
| Persistent file storage on Vercel | No | Blob |
| Scheduled jobs on Vercel | Loops (unreliable) | Cron routes and Queues |

---

## 12. Release plan

| Ticket | Work | Implements | Done when |
|---|---|---|---|
| R6-0 Platform fixes | Cron routes replace `lifespan` loops; storage interface with Blob; SYSTEM.md updated to Vercel; `fly.toml` removed | D6; 2.5, 4.2, 4.3 | Reconciliation runs from cron on Vercel; uploads persist across deployments |
| R6-1 Spaces and rooms | Models, migrations, permissions, derived membership, topics, posts, announcements with approval | D3; 5.1, 5.2, 6, 7 | A mobilizer sees only their ward room; tests cover every reach |
| R6-2 Console and Field app shells | Two layouts, Comms and Feedback in the sidebar, PWA install, push subscriptions, inbox | D2; 8; `M1` sidebar, `M2` tabs | A mobilizer installs the app and receives a push for a new announcement |
| R6-3 App meetings and calls | LiveKit tokens from FastAPI, meetings (audio first, video optional), host controls, one-to-one app calls, Start meeting on event cards | D6; 5.4; `M1`, `M2` Meeting | Two browsers hold a meeting; the host can mute, remove and bring someone on stage |
| R6-4 Phone bridge | `TelephonyProvider` (console, LiveKit SIP); dial-out, keypad hand-raise, Call my phone, LiveKit webhooks, call legs and costs, automatic retry, Ring again | D4, D8; 5.4, 6, 10; `M1` | In practice mode each dial is logged. On the pilot trunk a basic phone joins and raises a hand. An unanswered phone is rung twice more, 2 minutes apart, then shows No answer. Ring again places one immediate call and is refused after 3 re-dials. Every attempt is its own call leg with its cost |
| R6-5 Consent, preferences, budgets | Consent wording version, consent-check call, opt-out (press 9), quiet hours, limits, budgets, supporter-call approval | D7; 9 | A call outside the window or over budget is refused with a clear reason; an opt-out stops all further calls |
| R6-6 Feedback | Feedback items and history, keypad feedback calls | 4.4, 9; `M2` Room, Home | Each feedback item shows its status changes |
| R6-7 Field journal | Dexie storage, offline queue, idempotent sync | 4.4; `M2` Record | An entry made offline appears once on the server after reconnecting |
| R6-9 Bulk SMS compliance queue | `sms_runs`, `sms_outbox`; compliance gate; vetting step; queue worker with batches, rate, window and retries; delivery receipts; halt and apology; consent evidence export; Console run screen | D9, D10; 5.5, 6, 9, 10 | In practice mode a 5,000-recipient run goes out in batches with no request timeout. A message without the candidate's name, or with no language declared, is refused. A run approved at 17:55 sends what fits and resumes at 08:00. A STOP received mid-run skips that number. Halt stops the next batch. The consent evidence file downloads for any run |

R6-0 to R6-4 form the minimum viable release; R6-9 can follow R6-0 independently. Every ticket updates `contracts/frontend-api.json`
and both test suites, and leaves practice mode as the default.

---

## 13. Risks and open questions

| ID | Item | Proposed handling | Resolved |
|---|---|---|---|
| Q1 | Which SIP trunk provider, and does it accept connections from LiveKit Cloud abroad? | Confirm with Cloud One, Telkom and SautiKit before R6-4; otherwise move to the Kenyan VPS earlier | [ ] |
| Q2 | Who pays for calls and texts? | The campaign holds one communication budget covering calls and SMS | [ ] |
| Q3 | Vercel plan | Cron every few minutes (reminders) needs Pro; retries use Queues | [ ] |
| Q4 | Video in the field | Default audio-only; video by host choice | [ ] |
| Q5 | Recording meetings | Off in this release unless approved | [ ] |
| Q6 | CA internet telephony guidelines (2026 draft) | Licensed provider's numbers for the pilot; confirm the final licensing position before selling calling | [ ] |
| Q7 | SMS code retained but dormant | Superseded by A3: SMS is active through the queue | [x] |
| Q8 | Which licensed bulk SMS provider? | Sozuri chosen (A4); Africa's Talking kept as an alternative adapter | [x] |
| Q11 | Basic phones in meetings | Ask SautiKit (and Angani's cloud phone service) for a SIP trunk LiveKit can dial out through with a Kenyan number; otherwise confirm SautiKit's stream is two-way, its audio format, keypad events while streaming and concurrent call limits, and build the bridge | [ ] |
| Q9 | Current text of the CA political bulk SMS guidelines | The 2017 guidelines could not be downloaded from ca.go.ke; 5.5 follows the 2012 text and published summaries of 2017. Confirm clause by clause with the provider before go-live | [ ] |
| Q10 | Campaign period dates for 2027 | Set from the IEBC election timetable when gazetted | [ ] |

---

## 14. Out of scope for Release 6

Inbound calls, call-in numbers and missed-call callbacks; two-way SMS conversations (only STOP
and help keywords are handled); a knowledge library;
polling-station and election-day features; recording and transcription (unless Q5 is approved);
native iOS or Android apps.

---

## 15. Implementation tracker

| Ticket | Status | Branch or PR | Mockup checked | Contract updated | Tests pass |
|---|---|---|---|---|---|
| R6-0 | Not started | | n/a | [ ] | [ ] |
| R6-1 | Not started | | n/a | [ ] | [ ] |
| R6-2 | In progress (demo slice: PWA and push, `DM-R6` DM-5) | `demo-comms` | [ ] `M1`, `M2` | [x] | [x] |
| R6-3 | In progress (demo slice: LiveKit meetings for logins, `DM-R6` DM-4) | `demo-comms` | [ ] `M1`, `M2` | [x] | [x] |
| R6-4 | Not started | | [ ] `M1` | [ ] | [ ] |
| R6-5 | Not started | | n/a | [ ] | [ ] |
| R6-6 | Not started | | [ ] `M2` | [ ] | [ ] |
| R6-7 | Not started | | [ ] `M2` | [ ] | [ ] |
| R6-9 | In progress (demo slice: queue, gate, run screen, `DM-R6` DM-3) | `demo-comms` | [ ] `M1` | [x] | [x] |

Status values: Not started, In progress, In review, Done.

---

## 16. Amendments

| ID | Date | Change | Sections |
|---|---|---|---|
| A1 | 19 November 2026 | Missed phone participants are retried automatically (2 more attempts, 2 minutes apart) and the host can Ring again (up to 3 times per person per meeting); adds D8 | 1, 5.4, 6, 7, 9, 10, 12 |
| A2 | 23 November 2026 | One installation type, one candidate and one seat: D1 replaced, D3 narrowed to the campaign space, rule 7 and R6-8 withdrawn | Header, 1, 4, 5.1, 8, 9, 11, 12, 15 |
| A3 | 23 November 2026 | Bulk SMS through an outsourced licensed provider and the platform's compliance queue; D5 replaced by D9; D10 one queue service for calls and SMS; adds 5.5, two tables, rule 11, settings, R6-9, Q8 to Q10 | 1, 4, 5.5, 6, 9, 10, 11, 12, 13, 14, 15 |
| A4 | 23 November 2026 | Providers chosen: Sozuri (SMS), LiveKit (meetings; Cloud for pilot, Angani for production), SautiKit (basic phones, SIP or stream bridge); WhatsApp out; adds D11, Q11, resolves Q8; demo slice `DM-R6` defined | Header, 1, 13 |
| A5 | 24 November 2026 | No gamification: kudos, team challenges, ward boards, the weekly spotlight and the recognition rule removed; R6-6 is feedback only | 4.4, 6, 7, 8, 9, 11, 12 |
