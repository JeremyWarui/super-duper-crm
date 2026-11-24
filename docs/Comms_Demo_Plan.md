# Communications Demo Plan: SMS queue, online calls, PWA and push (Release 6 demo slice)

| | |
|---|---|
| Document ID | `DM-R6` |
| Version | 0.2, 23 November 2026 |
| Status | **Approved for implementation** |
| Parent design | `CD-R6` Communications Design (amendments A3, A4) |
| Mockups | [`design/R6_Mockups.html`](design/R6_Mockups.html): `M1` Console, `M2` Field app |
| Branch | `demo-comms`, from the branch holding the `targets-history` work |
| Tickets | `DM-0` to `DM-7` |

How to use this document: it is the work order for the implementation session (Claude Code
or a developer). Do the tickets in order. A ticket is done when every "Done when" line holds, the
tests listed pass, and its row in the tracker (section 10) is ticked. Where this document and
`CD-R6` differ, this document governs the demo; `CD-R6` governs the full release. Record any
deviation in section 11 before merging.

---

## 1. Purpose

Show, on real phones, that the CRM can:

1. **Send bulk SMS** through a licensed Kenyan provider (Sozuri), through the compliance queue,
   with delivery confirmed on screen.
2. **Hold online calls** (audio or video) between campaign team members, using LiveKit.
3. **Ring the team's phones** through the installed field app (PWA) with push notifications,
   so "Start call" reaches people without sharing a link.

Calls to offline (basic) phones are **out of scope**: they need a SIP trunk or the SautiKit
bridge, which are pending provider answers (`CD-R6` Q1, A4).

---

## 2. Decisions (from the 23 November 2026 discussion)

| ID | Decision |
|---|---|
| X1 | SMS provider: **Sozuri** (states it is licensed by the Communications Authority of Kenya). Africa's Talking stays in the code as an alternative provider |
| X2 | Meetings: **LiveKit**. Local `livekit-server --dev` for development; **LiveKit Cloud (free Build plan)** for the demo |
| X3 | Phone calls to basic phones (later): **SautiKit**, through SIP if offered, otherwise its audio stream and a bridge. Not in this demo |
| X4 | WhatsApp is out of scope: Meta's WhatsApp Business policy prohibits political parties, candidates and campaigns |
| X5 | Production hosting (later): LiveKit and any bridge on an **Angani** server in Nairobi; the CRM stays on Vercel and Neon |
| X6 | Practice mode stays the default everywhere: with no keys set, nothing is sent and nothing costs money |

---

## 3. Scope

**In:** Sozuri adapter and signed delivery reports; test SMS action; the SMS compliance queue (demo
version of `CD-R6` 5.5 and ticket R6-9); LiveKit meetings for logins (start, join, leave, audio
or video, attendance); PWA install; web push to ring invitees; demo data and script.

**Out:** basic phones in meetings; recorded-message calls; the full host panel (`M1` right
panel beyond a participant list); rooms and announcements (R6-1); feedback, recognition, journal;
call budgets; recordings.

---

## 4. Prerequisites

### 4.1 Accounts (the owner provides the keys; the build must work without them)

| Service | Needed | Settings |
|---|---|---|
| Sozuri | A **test project** (separate from the live project) with its own API key, signing secret, sender ID, callback URL and small balance | `SOZURI_PROJECT`, `SOZURI_SENDER_ID`, `SOZURI_API_KEY` and `SOZURI_SIGNING_SECRET` (starts szs_) and `SOZURI_AUTH_KEY` (starts szk_) |
| LiveKit Cloud | Project URL, API key and secret | `LIVEKIT_URL` and `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` |
| Web push | Generated once (see DM-6) | `VAPID_SUBJECT` (a `mailto:` address), `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` |
| Callbacks | A random secret in callback URLs | Existing `SMS_CALLBACK_SECRET` |

### 4.2 Rules for the implementation session

1. **Read the Sozuri API documentation first** (`https://sozuri.net/docs`, including its OpenAPI
   spec). Do not guess endpoint paths, field names, status values or authentication. If the
   documentation cannot be reached, stop and ask the owner to provide the OpenAPI file.
2. Follow existing patterns: the `SMSProvider` protocol in `services/sms.py`, the provider choice
   in `config.py`, permissions in `services/permissions.py` (`MAP`), refusals via
   `services/errors.py`, audit via `record(...)`.
3. Every API change updates `contracts/frontend-api.json`. Ruff (100-character lines) and both
   test suites must pass. Keep each file's existing line endings.
4. No secret is ever committed. New settings go in `.env.example` with empty values.
5. Practice mode first: build and test every ticket with no keys set, then with Sozuri's test
   project and the local LiveKit server, then live. Sozuri has **no sandbox host or test mode**:
   texts sent with any real key are delivered and charged.
6. Migrations are written by hand from autogenerate output, with names under 63 characters.

---

## 5. Tickets

### DM-0 Branch and settings

- Create branch `demo-comms`.
- `config.py`: extend `sms_provider` to `Literal["console", "africastalking", "sozuri"]`; add
  `sozuri_*` settings and a validator like the Africa's Talking one (live mode needs the key);
  add `livekit_url`, `vapid_*`, `livekit_api_key` and `livekit_api_secret`, and SMS queue settings:
  `sms_window` (default `08:00-18:00`), `sms_batch_size` (default 500), `sms_max_attempts`
  (default 3), `campaign_period_start`, `campaign_period_end` (dates; default unset = no limit
  in practice mode). Use `Africa/Nairobi` for all window checks.
- `setup.py` `services()`: add a "Meetings (LiveKit)" row and show `sozuri` as live SMS.
- Backend dependencies: `livekit-api`, `pywebpush`, `httpx` (if not present).
- Frontend dependencies: `livekit-client`, `@livekit/components-react`,
  `@livekit/components-styles`, `vite-plugin-pwa`.

**Done when:** the app starts with no new keys set; the services list shows SMS and Meetings
in practice mode; existing tests pass.

### DM-1 Sozuri SMS adapter and delivery reports

- `services/sms.py`: `SozuriSMSProvider` implementing `SMSProvider.send(recipients, message)`,
  returning `SendResult` with per-recipient `Recipient(phone, status, detail, message_id)`.
  Send in chunks the API allows; pass an idempotency key per chunk if Sozuri supports it.
  Map Sozuri's response to accepted and rejected recipients exactly as its documentation states;
  keep each recipient's `messageId` (40 hex characters) as `Recipient.message_id`, since delivery
  reports quote it. Base URL `https://sozuri.net/api`. `get_sms_provider` returns it when
  `SMS_PROVIDER=sozuri`. There is no sandbox: testing uses a separate Sozuri test project and key.
- Connection check: `SozuriSMSProvider.check()` calls `GET /api/v1/messaging/authtest`, which
  verifies the key and sends nothing. The setup and services page uses it for "Test connection".
- `api/routers/sms_callbacks.py`: add `POST /sms/{secret}/sozuri/delivery/` and
  `POST /sms/{secret}/sozuri/inbound/` (inbound replies, so STOP still opts out). Each request
  must pass, in order:
  1. the URL secret (`SMS_CALLBACK_SECRET`, as today; wrong or missing gets 404);
  2. the **`X-Sozuri-Signature`** header, formatted `t=<unix seconds>,v1=<64 lowercase hex>`:
     compute HMAC-SHA256, hex output, over the string `t` + `.` + the **raw request body byte
     for byte** (read the raw body before any JSON parsing), keyed with `SOZURI_SIGNING_SECRET`
     exactly as shown including the `szs_` prefix (not hex-decoded); compare with
     `hmac.compare_digest`; reject with 401 if missing, malformed or not matching;
  3. the timestamp: reject if `t` is more than 300 seconds from the server clock;
  4. optionally, the body's `authKey` equals `SOZURI_AUTH_KEY` (a weaker extra check only).
- Delivery report payload fields: `project`, `messageId`, `channel` (`sms`), `status`,
  `network`, `type` (`bulkDelivery`), `timestamp` (when Sozuri sent the webhook, not handset
  delivery time), `authKey`. Look the text up by `messageId`.
- `services/texting.py`: `apply_report` currently maps Africa's Talking statuses through
  `REPORTED`. Add a provider-specific mapping for Sozuri:

  | Network | Sozuri status | Internal status |
  |---|---|---|
  | Safaricom, Airtel | `success` | `delivered` |
  | Safaricom | `network_failure`, `delivery_impossible`, `absent_subscriber`, `unknown_error` | `failed` (store the status as the detail) |
  | Airtel | `failed` | `failed` |
  | Any | Anything else | Ignore and log |

- **Telkom numbers get no delivery webhooks.** Texts to Telkom numbers stay `sent` for good.
  Identify Telkom numbers by prefix at send time, mark them `no_report_expected` (a detail on
  the `SmsLog` row, not a new status), and show "Sent (Telkom sends no delivery report)" in the
  log. Run totals count them as sent, not as pending.
- Tests: send success, partial rejection, provider error, `authtest` check; delivery report
  applied once and repeat ignored; each Sozuri status mapped as in the table; unknown status
  ignored; wrong URL secret gets 404; missing, malformed or wrong signature gets 401; a
  timestamp 301 seconds old is rejected; a body changed after signing is rejected; a Telkom
  number is marked "no report expected". Use mocked HTTP and fixed signatures computed in the
  test; no real calls in tests.

**Done when:** with `SMS_PROVIDER=sozuri` and the test project's key, "Test connection" passes,
a text to a Safaricom or Airtel number is accepted and its `SmsLog` row moves to `delivered` when
the signed report arrives, a forged report is rejected, and all new tests pass.

### DM-2 Test SMS action

- `POST /console/sms/test/` (permission `sms.send`): body `{phone, body}`; normalises the
  number; sends one text through the provider (bypassing the queue, purpose `test`); records
  `SmsLog` and an audit entry. Refuses outside practice mode unless the number belongs to a
  supporter with consent or a login of the campaign (prevents misuse).
- Console: a "Send test SMS" form under Messages, and a status column (Sent, Delivered, Failed)
  in the SMS log that refreshes every 10 seconds while any row is not final.

**Done when:** the demo person's phone receives the test text and the log shows Delivered.

### DM-3 SMS compliance queue (demo version of `CD-R6` 5.5, R6-9)

- Models and migration: `sms_runs` and `sms_outbox` with the fields in `CD-R6` section 6;
  unique `(run_id, phone)` on the outbox.
- `services/messages.py` `send`: approval creates a run instead of sending directly. The run
  holds `targeted`, `excluded_no_consent`, `excluded_opted_out` counts.
- Compliance gate (`services/sms_queue.py`), at approval and before every batch:
  1. the body contains the candidate's name as registered;
  2. language declared `en` or `sw` (new field on the draft, confirmed by the approver);
  3. only supporters with `consent_given` and a consent wording that covers SMS;
  4. numbers in `sms_opt_outs` are skipped, including opt-outs received mid-run;
  5. the opt-out line ("Reply STOP to stop") is appended and counted in `parts_of`;
  6. sending only inside `sms_window` (never wider than 08:00 to 18:00 Nairobi time) and inside
     the campaign period when set;
  7. a run with vetting required stays `awaiting_vetting` until a vetting reference is entered
     (a settings flag `SMS_VETTING_REQUIRED`, default off for the demo).
  A failed check refuses with a clear reason; nothing is sent around it.
- Worker: `process_next_batch(run_id)` takes up to `sms_batch_size` queued rows, sends them,
  marks rows `sent` or `failed`, retries transient failures with growing delay up to
  `sms_max_attempts`, and never resends a row the provider accepted.
  - Trigger 1: on approval, process the first batch immediately (within the request, bounded
    by batch size).
  - Trigger 2: a protected route `POST /internal/sms/drain/` (header `CRON_SECRET`) that
    processes due batches; wired to Vercel Queues if available on the account, otherwise to a
    Vercel cron entry, and callable by hand for the demo.
  - Trigger 3: a CLI command `campaign-crm sms-worker` that loops locally (for development and
    self-hosting).
  - Outside the window, the run shows "Waiting until 08:00" and resumes then.
- Halt, Pause, Resume: candidate or manager; Halt stops the next batch and records the reason.
- Consent evidence: `GET /campaigns/{id}/sms-runs/{run_id}/consent.csv` (candidate, manager).
- Console run screen (`M1` Comms): stage, counts, estimated and actual cost, Pause, Resume,
  Halt, and the consent download.
- Tests: each gate check refuses with its reason; a run of 1,200 recipients in practice mode
  completes in 3 batches; a mid-run STOP is skipped; Halt stops further batches; a retried
  batch does not duplicate an accepted number; window edge behaviour at 17:59 and 18:00.

**Done when:** approving a message to a test ward sends in batches, the run screen reaches
Completed with Delivered counts, and a message without the candidate's name is refused.

### DM-4 Online meetings with LiveKit

- Models and migration (subset of `CD-R6` section 6): `meetings` (id, campaign_id, title, mode
  `audio` or `video`, host_id, event_id nullable, livekit_room, status `live` or `ended`,
  started_at, ended_at) and `meeting_attendance` (meeting_id, user_id, joined_at, left_at).
- Permissions in `MAP`: `meetings.start` for candidate, manager, comms, coordinator (area);
  `meetings.join` for any login of the campaign. Add refusal texts.
- Routes:
  - `POST /campaigns/{id}/meetings/` start: creates the LiveKit room (server API), stores the
    meeting, notifies invitees (DM-5), returns the meeting and a join link `/meet/{meeting_id}`.
  - `GET /meetings/{id}/token/` returns a short-lived LiveKit access token (15 minutes) for the
    signed-in user, room-scoped; publish permissions follow the mode (no camera publish in
    `audio` meetings).
  - `POST /meetings/{id}/end/` host ends the meeting (closes the LiveKit room).
  - `POST /livekit/webhook/` verifies the LiveKit signature (`livekit-api` webhook receiver)
    and records joins, leaves and room end into `meeting_attendance` and `meetings`.
- Frontend:
  - Console "Start call" dialog: title, audio or video, invite (whole campaign or a ward),
    shows the join link with copy and QR (existing `qrcode.react`).
  - `/meet/:meetingId` page: LiveKit `PreJoin`, then `VideoConference` for video or an audio
    participant list with speaking indicators for audio; control bar (mute, camera, leave);
    host sees "End for everyone". Styled with the CRM's tokens. Works in a phone browser.
  - Console "Calls" list: past meetings with attendance and duration.
- Practice mode: with no LiveKit keys, start refuses with "Meetings are not configured" and
  the services list says so. Development uses `livekit-server --dev` (`LIVEKIT_URL=ws://localhost:7880`).
- Tests: token is room-scoped and expires; a login of another campaign cannot get a token;
  audio meetings deny camera publish; webhook with a bad signature is rejected; attendance
  recorded from joined and left events.

**Done when:** on LiveKit Cloud, the host starts a video call, the demo person joins from a
phone browser, both see and hear each other, and the Calls list shows both attendances.

### DM-5 PWA and push notifications

- PWA (`vite-plugin-pwa`): manifest (name, short name, icons 192 and 512, theme colour from the
  CRM theme, `display: standalone`, start URL the field app home); service worker with
  `injectManifest` so it can handle push.
- Push:
  - Model and migration: `push_subscriptions` (user_id, endpoint unique, p256dh, auth,
    created_at, last_used_at).
  - Routes: `GET /push/key/` (public VAPID key), `POST /push/subscribe/`,
    `DELETE /push/subscribe/`.
  - Service `services/push.py`: `notify(users, title, body, url)` with `pywebpush`; deletes
    subscriptions that return 404 or 410.
  - Meeting start (DM-4) notifies invitees: "Joining: {title}" with the URL `/meet/{id}`.
  - Service worker: shows the notification; on click, focuses or opens the app at the URL.
  - Field app: an "Enable call alerts" prompt after sign-in (never on first load), with an
    iPhone note: alerts work after "Add to Home Screen" (iOS 16.4 or later).
- Tests: subscribe and unsubscribe; expired subscription removed on 410; meeting start calls
  `notify` with invitees only.

**Done when:** the demo person installs the field app on their phone, enables alerts, and
receives a notification when the host presses "Start call"; tapping it opens the meeting.

### DM-6 Settings, keys and deployment

- A CLI command `campaign-crm make-vapid-keys` printing a new key pair for `.env`.
- `.env.example`, `backend/README.md` and `DEPLOY.md`: every new setting, where to get it, and
  the callback URLs to paste into the Sozuri and LiveKit dashboards:
  - Sozuri delivery: `https://<api-host>/sms/<SMS_CALLBACK_SECRET>/sozuri/delivery/`
  - Sozuri inbound: `https://<api-host>/sms/<SMS_CALLBACK_SECRET>/sozuri/inbound/`
  - Copy each Sozuri project's signing secret (`szs_...`) and auth key (`szk_...`) into the
    settings; the test and live projects have different keys and secrets.
  - LiveKit webhook: `https://<api-host>/livekit/webhook/`
- Vercel: add the queue or cron entry for `/internal/sms/drain/` to `vercel.json`.

**Done when:** a fresh deployment with the keys set passes the demo script in section 7.

### DM-7 Demo data and documentation

- Demo seed: a test ward, two consenting demo supporters (numbers entered at demo time, never
  committed), and a draft message that passes the gate and one that fails it (missing name).
- `docs/Demo.md`: add the demo script below.
- Update `CD-R6` tracker rows for the parts delivered (R6-2 PWA and push, R6-3 meetings, R6-9
  queue) as "In progress (demo slice)".

---

## 6. Data and API summary

| New table | Ticket |
|---|---|
| `sms_runs`, `sms_outbox` | DM-3 |
| `meetings`, `meeting_attendance` | DM-4 |
| `push_subscriptions` | DM-5 |

| New route | Permission |
|---|---|
| `POST /console/sms/test/` | `sms.send` |
| `POST /sms/{secret}/sozuri/delivery/` | URL secret (and signature if provided) |
| `POST /internal/sms/drain/` | `CRON_SECRET` |
| `GET /campaigns/{id}/sms-runs/`, `POST .../{run_id}/pause/`, `.../resume/`, `.../halt/` | `sms.send` |
| `GET /campaigns/{id}/sms-runs/{run_id}/consent.csv` | `sms.send` |
| `POST /campaigns/{id}/meetings/`, `POST /meetings/{id}/end/` | `meetings.start` |
| `GET /meetings/{id}/token/` | `meetings.join` |
| `POST /livekit/webhook/` | LiveKit signature |
| `GET /push/key/`, `POST` and `DELETE /push/subscribe/` | Signed in |

---

## 7. Demo script (about 8 minutes)

1. The demo person opens the field app link on their phone, signs in, installs it ("Add to
   Home Screen") and enables call alerts.
2. Console, Messages: "Send test SMS" to the demo person (a Safaricom or Airtel number, since
   Telkom sends no delivery reports); their phone receives it; the log shows Delivered.
3. Draft a message to the test ward without the candidate's name; approval is refused with the
   reason. Add the name, approve; the run screen shows the checks passed, batches sent and
   Delivered counts.
4. Console: "Start call", video. The demo person's phone shows the alert; they tap it and join.
   Talk, mute, switch camera.
5. End the call; start an audio-only call to show the low-data mode.
6. Open Calls: both meetings with attendance and duration.

Run the demo between 08:00 and 18:00 so the SMS window allows sending (or show the
"Waiting until 08:00" state as a feature).

---

## 8. Costs for the demo

LiveKit Cloud Build, Vercel Hobby, Neon free, web push: free. Sozuri has no free sandbox: the
test project needs a small balance, and real texts cost under KES 1 each. No sender ID fee until
going live (confirm Sozuri's default sender for the test project).

---

## 9. Open questions

| ID | Item | Handling |
|---|---|---|
| DQ1 | Sozuri API details (send endpoint and response, idempotency, inbound payload) | Read `sozuri.net/docs` (Text API, Request Headers, Webhooks) before DM-1; signatures, delivery fields and statuses are confirmed in DM-1 |
| DQ2 | Vercel Queues on the current plan | If unavailable, use the cron entry plus the manual drain for the demo |
| DQ3 | Sender ID while testing | Confirm Sozuri's default or shared sender for test traffic |
| DQ4 | Political content rules for demo texts | Keep demo texts neutral ("Test from the campaign CRM") |

---

## 10. Implementation tracker

| Ticket | Status | Branch or PR | Mockup checked | Contract updated | Tests pass |
|---|---|---|---|---|---|
| DM-0 | Done | `demo-comms` | n/a | [x] | [x] |
| DM-1 | Done (live Sozuri check pending keys) | `demo-comms` | n/a | [x] | [x] |
| DM-2 | Done (real phone pending keys) | `demo-comms` | n/a | [x] | [x] |
| DM-3 | Done | `demo-comms` | [x] `M1` Comms (no run detail in the mockup; built from 5.5) | [x] | [x] |
| DM-4 | Done (call on LiveKit Cloud pending keys) | `demo-comms` | [ ] `M1`, `M2` Meeting | [x] | [x] |
| DM-5 | Done (phone install and alert pending keys) | `demo-comms` | [ ] `M2` | [x] | [x] |
| DM-6 | Done (fresh deployment pending keys) | `demo-comms` | n/a | n/a | n/a |
| DM-7 | Done | `demo-comms` | n/a | n/a | n/a |

Status values: Not started, In progress, In review, Done.

---

## 11. Deviations

| Date | Ticket | Deviation and reason |
|---|---|---|
| 23 November 2026 | DM-1 | Version 0.2: Sozuri has no sandbox, so testing uses a separate test project; callbacks verified by `X-Sozuri-Signature` (HMAC-SHA256, 300-second window); Sozuri status mapping added; Telkom sends no delivery reports |
| 24 November 2026 | DM-1 | The setup wizard's SMS "Test" runs `check()` (authtest, sends nothing) when the provider is Sozuri; other providers still send a test text. Telkom is taken as numbers starting +25477 |
| 24 November 2026 | DM-3 | No scheduler drains the queue: the owner paused the cron. The first batch goes at approval; later batches and runs held outside the window go by `POST /api/internal/sms/drain/` by hand or `campaign-crm sms-worker`. Vercel Hobby allows one cron run a day and Vercel Queues are beta (DQ2) |
| 24 November 2026 | DM-3 | Gate 3 reads a wording as covering texts when it mentions SMS, text or contact. The mobilizer wording ("hold these details") does not, so contacts recorded by mobilizers are counted as `excluded_no_consent` and not texted. The demo seed now records that wording |
| 24 November 2026 | DM-3 | The opt-out line stays "Reply STOP to opt out." (already in use) rather than "Reply STOP to stop". Cost uses `SMS_PART_PRICE_CENTS` (default 80, KES 0.80 a part) |
| 24 November 2026 | DM-4 | Coordinators start calls only for a ward of theirs; the host, the candidate or the manager ends a call. The Calls page is a new "Reach out" item |
| 24 November 2026 | DM-5 | The service worker caches nothing (alerts only), so a deploy is never served stale. Two PNG icons (192, 512) added in `frontend/public` |
| 24 November 2026 | DM-6 | Callback URLs carry `/api` (every route is mounted there): `https://<api host>/api/sms/<secret>/sozuri/delivery/`, `.../sozuri/inbound/`, `https://<api host>/api/livekit/webhook/`. No `vercel.json` cron (see DM-3) |
| 24 November 2026 | DM-7 | `campaign-crm demo-comms --phone <a> --phone <b>` adds the two demo contacts in a ward with nobody else and the two drafts; the numbers are typed at demo time |
| 24 November 2026 | DM-3 | After the critic pass: each batch is claimed with a conditional update, so two workers never take the same number; each batch keeps one idempotency key across retries, so a lost answer is a repeat at Sozuri and not a second text; `SMS_BATCH_SIZE` is capped at 500 (one Sozuri request); a 4xx refusal fails the batch for good; run stages change only from the stage expected, so Halt or Pause during a batch is kept; consent, withdrawal and erasure are re-checked before every batch, and erasure takes the number out of runs; rows left `sending` by a crashed worker are sent again after 15 minutes under the same key |
| 24 November 2026 | DM-3 | Approval requires the approver to send the language (`{language}` on `POST /messages/{id}/send/`) |
| 24 November 2026 | DM-5 | Call alerts go only to https addresses of the browsers' push services (Google, Mozilla, Apple, Microsoft); signing out unsubscribes the device |
| 24 November 2026 | DM-3 | Event invitations go through the queue as runs tied to the event (`sms_runs.event_id`), with the same gate, window and batches; the event's number reached follows what the run sent |
