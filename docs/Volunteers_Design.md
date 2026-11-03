# Release 5: Volunteers, Member Sign-in and Candidates

Technical design for volunteers as the UI designs in
`docs/party-platform-design/party-platform-design/` describe them
(`DESIGN_HANDOFF.md`; screens `Join`, `SignIn`, `SysCode`, `SysChooser`,
`MemberAccount`, `Candidates`, `Candidate`), keeping the registration fields of
the sample at `teamndiritumuriithi.co.ke/register`. The screens are visual and
behavioural reference rebuilt in our React stack; they are not copied as code.
It builds on `docs/Identity_Access_Design.md` (members, volunteers, the
`party_requests` queue) and `docs/Website_Design.md` (public site, `/signin`).

Status: draft for approval, 3 November 2026. Section 6 lists the choices that
need Jeremy's answer before R5-2.

Direction set by Jeremy on 3 November 2026, after R5-1:

1. **A volunteer is a party member.** The Join form's "Volunteer for events"
   tick opens the sample's fields: first and last name, email, phone, polling
   station, profession, the ten volunteer areas with Other.
2. **Volunteers sign in the designs' way:** phone, then a 6-digit SMS code,
   then their account. `SMS_PROVIDER=console` prints the code in the API's log;
   live use needs an SMS provider.
3. **Public Candidates directory and Candidate profile pages**, whose "I'll
   volunteer" form goes to that campaign only.

This replaces the design approved earlier on 3 November: volunteers are no
longer standalone, they get a sign-in, and the party `/volunteer` page and the
campaign `/volunteer/<code>` page are not built. It also reverses
`Implementation_Plan.md` "Volunteers have no login" for party volunteers.

Kept from Release 1: the volunteer consent box is separate from the
membership consent and its wording is stored (Data Protection Act, 2019); a
public form answers the same whatever the register holds; party and campaign
data never mix.

---

## 1. What exists today

| Piece | Where | What R5 does |
|---|---|---|
| Join with a volunteer part | `/join-party` (`pages/public/JoinParty.jsx`); `POST /api/party/join/`; `services/membership.py` `request_join` queues it; `services/volunteers.py` `apply_part` writes the profile when the join adds or re-pends the member | Kept. The part gains the sample's fields; the page is rebuilt on `Join.dc.html` |
| Volunteer profiles | `models/party.py` `VolunteerProfile`; R5-1 (`volunteer_register`) added `campaign_id`, own name, phone, email, ward, centre, profession, `interest_other`, and made `member_id` optional | See "R5-1: what stays and what reverts" |
| Profile follows the member | `follow_member`, `follow_withdrawal` | Kept unchanged |
| Officer register | `/party/volunteers`, `api/routers/party_volunteers.py`, CSV | Shows the new fields and areas; party rows only |
| Volunteer withdraw link | `/party/volunteer/withdraw/<code>`, queued | Kept |
| Sign-in | `POST /api/auth/login/` username and password; `auth_tokens`, one per `users` row; `Authorization: Token <key>` | Unchanged for staff and campaign logins. Members get a separate phone sign-in |
| SMS | `services/sms.py`; `ConsoleSMSProvider` logs only counts | The console provider also logs the message text |
| Aspirants and campaigns | `aspirants` (member, seat, area, status, `campaign_id`); `campaigns` (title, seat, area, sign-up code); `api/routers/join.py` `_access` (active, grace, read-only, locked) | Read by the public directory; a campaign gets a public profile |
| Party events | `party_posts` of kind event, `GET /api/party/posts/?kind=event` | Listed on the member account |

### R5-1: what stays and what reverts

R5-1 (`a8344f6`, migration `volunteer_register`) is not rolled back. Under
the new direction:

| R5-1 piece | Verdict | Why |
|---|---|---|
| `campaign_id` (NULL = party) | Stays | Candidate profile volunteers are campaign rows |
| `first_name`, `last_name`, `phone`, `email`, `ward_id` | Stay | Campaign volunteers have no member row. On a party row they are copied from the join, as R5-1's `apply_part` already does |
| `registration_centre_id`, `profession`, `profession_other`, `interest_other` | Stay | The sample's fields |
| Unique `(phone)` for party rows, `(campaign_id, phone)` | Stay | |
| `member_id` optional, to be dropped in R5-2 | **Reverts** | A party volunteer is a member again. R5-2 keeps `member_id` and adds `CHECK ((campaign_id IS NULL) = (member_id IS NOT NULL))`: a party row has a member, a campaign row has none. `uq_volunteer_profiles_member_id` stays |
| Plan to remove the join form's volunteer part and `apply_part` | **Reverts** | The tick on Join is the way in |

---

## 2. Design

### Principles

1. **One register, two owners.** A party volunteer is a member's profile
   (`member_id` set, `campaign_id` NULL). A campaign volunteer is campaign
   data (`campaign_id` set, no member): only that campaign's manager sees it,
   deleting the campaign deletes it, and the party register, CSV and
   dashboard never read it. Someone may be both, as two unlinked rows.
2. **Public forms do not show who is registered.** The join stays one queued
   insert. Asking for a sign-in code is one insert whatever the phone, and the
   SMS goes out after the answer. A campaign volunteer form answers the same
   for a new or a known phone.
3. **A member session is not a login.** Members never get a `users` row. Their
   token lives in its own table and is accepted only by `/api/account/`
   routes; staff and campaign routes refuse it, and the member routes refuse a
   staff or campaign token.

### Data model

Three revisions, in this order: `volunteer_areas` (R5-2), `member_sign_in`
(R5-4), `campaign_profiles` (R5-6).

#### `volunteer_profiles` (R5-2, `volunteer_areas`)

| Change | Rule |
|---|---|
| `member_id` | Kept; `CHECK ((campaign_id IS NULL) = (member_id IS NOT NULL))` |
| `interests` | JSON list of `VolunteerArea` values; at least one on a party row |
| Old interests | Mapped: `mobilisation` → `mobilising_voters`; `social_media`, `fundraising` as they are; the rest → `other` with their label in `interest_other` (no live data; this keeps the dev database whole) |

`VolunteerArea` (replaces `VolunteerInterest`): `fundraising`,
`door_to_door`, `mobilising_voters`, `social_media`, `recruiting`,
`materials`, `data_collection`, `community_listening`, `barazas`, `other`;
labels as on the sample ("Holding Barazas & Household Meetings").

#### `sign_in_codes` (R5-4, new)

| Column | Rule |
|---|---|
| `id` | UUID |
| `phone` | normalised Kenyan mobile, indexed |
| `code_hash` | HMAC-SHA256 of the code with `SECRET_KEY`; the code itself is never stored |
| `expires_at` | 10 minutes after sending |
| `tries_left` | 3 |
| `created_at` | for the 45-second resend wait and the hourly cap |

A new code for a phone deletes that phone's older codes. A spent, expired or
exhausted code is deleted.

#### `member_tokens` (R5-4, new)

| Column | Rule |
|---|---|
| `id` | UUID |
| `member_id` | FK `party_members` ON DELETE CASCADE, unique (one live session per member) |
| `key` | 40 characters, unique |
| `expires_at` | 30 days after sign-in |

#### `campaign_profiles` (R5-6, new)

| Column | Rule |
|---|---|
| `campaign_id` | PK, FK `campaigns` ON DELETE CASCADE |
| `photo_url` | `https://` URL or `''`, as party leaders' photos |
| `slogan` | `varchar(120)` |
| `bio` | text, at most 2,000 characters |
| `priorities` | JSON list of up to 3 `{title, text}`, title ≤ 80, text ≤ 300 |
| `office_address`, `office_phone`, `office_email` | optional |
| `published` | bool, default false; set by the manager |
| `hidden_by_party` | bool, default false; set by the superuser (see decision 4) |

### Joining as a volunteer (R5-2, R5-3)

`POST /api/party/join/` changes:

| Field | Rule |
|---|---|
| `first_name`, `surname` | replace `full_name` (Join.dc.html asks for both); stored as `party_members.full_name = "first surname"`, and on the volunteer row as they were typed |
| `email` | optional, required when `volunteer` is sent (as on the sample) |
| `volunteer.registration_centre` | required; must lie in `ward`. Asked only with the tick (decision 3) |
| `volunteer.profession`, `profession_other` | required; text required when `other` |
| `volunteer.areas`, `area_other` | one or more `VolunteerArea`, no repeats; text required when `other` |
| `volunteer.preferred_contact`, `consent_given` | kept |

The registration centres of a ward come from
`GET /api/party/places/?ward=<id>` (added to the existing route).
`apply_part` writes the new fields. Nothing else in the queue changes.

### Member sign-in (R5-4, R5-5)

| Route | Does |
|---|---|
| `POST /api/member-auth/code/` `{phone}` | Answers 202 and the same text for any well-formed phone: "If this number belongs to a party volunteer, a code is on its way." Writes a code row for every well-formed phone. After the answer, a background task sends the SMS only when the phone can sign in. Refuses with 429 after 10 requests an hour from one device, or a second request for one phone within 45 seconds, or a sixth in an hour |
| `POST /api/member-auth/verify/` `{phone, code}` | Right code, unexpired, tries left, and the phone can sign in: deletes the code, replaces the member's token and answers `{token, first_name}`. Otherwise one answer, "That code didn't match.", with `tries_left`; the third miss deletes the code |
| `POST /api/member-auth/logout/` | Deletes the member's token |

**Who can sign in:** an `approved` member whose volunteer profile is not
`withdrawn` (decision 1). A pending, suspended, rejected or withdrawn member
cannot. Every `/api/account/` request rechecks this, so an officer suspending
a member or the volunteer stopping ends the session at the next request.

Tokens are sent as `Authorization: Member <key>`. `get_signed_in_user`
already refuses any scheme but `Token`; the new `get_signed_in_member`
accepts only `Member`.

`services/sms.py` `ConsoleSMSProvider` logs each message's text at INFO, so
the code shows in the API's terminal during local work. The SMS reads:
"<Party short name> code: 123456. It expires in 10 minutes. Do not share it."

### The volunteer's account (R5-4, R5-5)

Built on `MemberAccount.dc.html`, with only what our data holds. Tasks are
deferred in `Implementation_Plan.md`, so the tasks area is an empty state.

| Part | Shows | Route |
|---|---|---|
| Header | "Habari, <first name>", Public site, Sign out | |
| Member card | Full name; branch (ward, county); member since (month and year of `party_members.created_at`, the application); status pill | `GET /api/account/` |
| Tab: My volunteering | Volunteer status (Interested, Active, Inactive); areas, polling station, profession, preferred contact; "Change my volunteer details" (the same fields as the Join form's volunteer part; centre within the member's ward); "My volunteer tasks" with the line "No tasks yet. Your branch will contact you when there is something to do."; the line "Volunteering for a candidate's campaign happens on their profile page", linking to `/candidates` | `GET /api/account/`, `PATCH /api/account/volunteer/` |
| Tab: Party events | Upcoming published party events, soonest first, each linking to its page | `GET /api/party/posts/?kind=event` (existing, public) |
| Tab: My data & privacy | Name, phone (masked `07•• ••• 678`), email, ward; the membership and volunteer consents with their wording and dates; "Stop volunteering" (withdraws the volunteer profile, keeps membership, ends the session); "Leave the party" (queues the same withdrawal as the member's link, ends the session); to correct name, phone or ward, the party office's contact | `POST /api/account/volunteer/stop/`, `POST /api/account/leave/` |

A volunteer's own changes are audited as `volunteer.self_update` (field names
only) and `volunteer.status` with actor "member". "Stop volunteering" uses the
existing move to `withdrawn`; "Leave the party" uses `request_withdraw` with
the member's withdraw code, so the officer flow and `follow_withdrawal` are
unchanged.

**Chooser (decision 2):** after a code, the account opens directly. When the
member also has a staff or campaign login (`users.party_member_id`), a
"Where to?" screen (`SysChooser.dc.html`) lists My membership plus each such
login's area, and those entries open the existing password sign-in. The phone
code never signs into a `users` login.

### Candidates (R5-6, R5-7)

| Route | Does |
|---|---|
| `GET /api/candidates/?seat=&county=&q=` | Public. Listed campaigns (below): name, seat, area, county, photo, slogan, and a slug `<seat>-<area-name>-<short id>` |
| `GET /api/candidates/{slug}/` | Public. The above plus bio, priorities, office contacts, and whether volunteering is open, with the campaign's wards |
| `POST /api/candidates/{slug}/volunteer/` | Public. First and last name, phone, ward (inside the campaign's area), consent (decision 6). Writes a campaign volunteer row; a known phone is left as it is; the answer and a withdrawal link are the same either way. 20 an hour per device |
| `POST /api/candidates/volunteer/withdraw/{code}/` | Deletes the campaign volunteer; the same answer for any code |
| `GET`, `PUT /api/campaigns/{id}/profile/` | The campaign's manager edits the profile and its `published` tick |
| `GET /api/campaigns/{id}/volunteers/`, `PATCH .../volunteers/{vid}/` | The manager lists (search, ward, status) and moves a volunteer to active or inactive, with notes |
| `PATCH /api/party/candidates/{campaign_id}/` `{hidden_by_party}` | Superuser hides or shows a profile (decision 4) |

**Listed** when the aspirant is `approved`, the profile is `published` and
not `hidden_by_party`, and the campaign's access is active, grace
period or read-only (not pending payment, locked, cancelled, or no
subscription at all).
**Volunteering open** when listed and access is active or grace period (the sign-up
link's rule without its `signups_open` switch, which belongs to supporters).

The directory shows one list ("Aspirants") with filters for seat, county and a
name or area search; the designs' Nominees tab needs primaries, which are not
in scope. The profile page shows About (bio), Priorities, the "Support
<first name>" form and the campaign office; the designs' Events and News tabs
are not built (decision 7).

The campaign routes join `CAMPAIGN_READS` / writes in
`tests/test_route_guards.py`; read-only and locked campaigns refuse the
writes as usual.

### Frontend

| Where | Change |
|---|---|
| `pages/public/JoinParty.jsx` | Rebuilt on `Join.dc.html`: three steps (Your details; Your branch with the "Volunteer for events" tick opening the sample's fields; Consent) and the done screen with withdrawal links. No national ID, date of birth, sex, leagues, declaration or fee |
| `components/Login.jsx` (rendered by `SignInPage` in `Gate.jsx`, `/signin`) | Rebuilt on `SignIn.dc.html` with two tabs; their grouping is decision 2. One tab sends a phone code, the other is today's username and password form |
| `pages/public/SignInCode.jsx` (`/signin/code`) | `SysCode.dc.html`: six-digit box, tries left, resend after 45 s, use a different number. No voice call |
| `pages/public/Chooser.jsx` (`/signin/where`) | `SysChooser.dc.html`, shown only by decision 2's rule |
| `pages/member/Account.jsx` (`/account`) | `MemberAccount.dc.html` with the parts above |
| `pages/public/Candidates.jsx` (`/candidates`), `Candidate.jsx` (`/candidates/:slug`) | `Candidates.dc.html`, `Candidate.dc.html` as above |
| `/candidates/volunteer/withdraw/:code` | Campaign volunteer withdrawal |
| `components/PublicLayout.jsx` | Menu gains Candidates; Sign in stays |
| `pages/campaign/Profile.jsx`, `pages/campaign/Volunteers.jsx` | Manager: edit and publish the profile; the volunteer list |
| `pages/party/Volunteers.jsx` | New areas, polling station, profession |
| `pages/party/Website.jsx` | Superuser: candidates list with Hide/Show |

The member token is stored apart from the staff token, so signing in as a
member never signs a staff or campaign login out.

---

## 3. Tickets

Migrations run one at a time, in ticket order (R5-2, R5-4, R5-6). A route
enters `contracts/frontend-api.json` in the frontend ticket that first calls
it. Each ticket gets one cold critic judged on its text and section 4 only.

**R5-1 Volunteer register schema** (done, `a8344f6`).

**R5-2 Volunteer areas and the join's volunteer part** (backend)
- Files: revision `volunteer_areas`; `models/enums.py` (`VolunteerArea`), `models/party.py` (CHECK), `schemas/party.py`, `services/volunteers.py` (`apply_part`, filters), `services/membership.py`, `services/dashboard.py`, `schemas/dashboard.py`, `api/routers/party.py` (join, places by ward), `api/routers/party_volunteers.py`, tests; `backend/evals/test_inbox_constant_work.py`, whose join payload and `VOLUNTEER_PART` change.
- Tests: a join with the volunteer part stores centre, profession and areas on the member's profile; a centre outside the ward, `other` without text, and a missing email are refused; a party row without a member and a campaign row with one fail at the database; the register, CSV and dashboard leave campaign rows out.

**R5-3 Join page and party volunteer pages** (frontend; depends R5-2)
- Files: `pages/public/JoinParty.jsx`, `pages/party/Volunteers.jsx`, `pages/party/Dashboard.jsx`, `pages/party/helpers.js` (areas and labels), `api/hooks`, contract, tests.
- Tests: the tick shows and requires the volunteer fields; the request carries what the route takes; centres load for the chosen ward; the officer register filters by the new areas and shows profession and polling station.

**R5-4 Member sign-in and account API** (backend)
- Files: revision `member_sign_in`; `models/member_auth.py`; `services/member_auth.py`, `services/sms.py`; `api/deps.py` (`get_signed_in_member`); `api/routers/member_auth.py`, `api/routers/account.py`; `config.py` if a setting is needed; tests.
- Tests: the code route answers the same for a volunteer, a non-member and a pending member, and writes one row each, and only the volunteer's phone gets an SMS; a right code signs in once; three misses spend the code; an expired code fails; a member token is refused by a staff route and a staff token by `/api/account/`; suspending the member makes the next account request 401; "Stop volunteering" and "Leave the party" end the session; the console provider logs the code.

**R5-5 Sign-in and account pages** (frontend; depends R5-4)
- Files: `components/Login.jsx`, `SignInCode.jsx`, `Chooser.jsx`, `pages/member/Account.jsx`, `Gate.jsx`, `api/hooks`, `store`, contract, tests.
- Tests: Send code moves to the code page; a wrong code shows tries left; a right code opens the account, or the chooser for a member with a linked login; the account shows the card, the volunteer details and the empty tasks state; a 401 returns to `/signin`.

**R5-6 Campaign profiles, directory and campaign volunteers API** (backend)
- Files: revision `campaign_profiles`; `models/campaign.py`; `schemas/candidates.py`; `services/candidates.py`, `services/volunteers.py`; `api/routers/candidates.py`, `campaigns.py`, `party.py`; `tests/test_route_guards.py`; tests.
- Tests: only listed campaigns appear (a draft aspirant, an unpublished, hidden, locked or pending-payment campaign do not); a ward outside the campaign's area is refused; a read-only campaign's form is closed; a known phone gets the same answer and no second row; the manager sees only their campaign's volunteers, another campaign's id answers 404, and the candidate and a mobilizer get 403; withdrawal deletes and answers the same for any code; deleting the campaign deletes its volunteers.

**R5-7 Candidates and manager pages** (frontend; depends R5-6)
- Files: `Candidates.jsx`, `Candidate.jsx`, the withdraw page, `pages/campaign/Profile.jsx`, `pages/campaign/Volunteers.jsx`, `helpers.js` (manager menu), `pages/party/Website.jsx`, `PublicLayout.jsx`, `Gate.jsx`, `api/hooks`, contract, tests.
- Tests: filters narrow the list; the profile's form offers only the campaign's wards and shows closed when volunteering is closed; the manager publishes a profile and lists volunteers.

**R5-8 Integration** (lead)
- Both test lanes; `backend/evals/`; demo seed (one published profile, one volunteer member who can sign in); `docs/SYSTEM.md`; one release critic against section 4 only.

---

## 4. Rubric for the critics (frozen once approved)

A critic judges these points and nothing wider. A finding outside them is
listed as non-blocking under Known gaps.

1. The Join form's "Volunteer for events" tick asks for and requires email, polling station (within the chosen ward), profession (Other with text) and one or more of the ten areas (Other with text), preferred contact and volunteer consent; without the tick none of them are asked. The result is a member with a volunteer profile carrying those values and the stored consent wording.
2. A party volunteer row always has a member and a campaign volunteer row never does, enforced by the database.
3. Asking for a sign-in code gives the same answer and writes one row for any well-formed phone; only an approved member with a non-withdrawn volunteer profile receives an SMS and can complete sign-in. With `SMS_PROVIDER=console` the code appears in the API log.
4. A code works once, within 10 minutes, and is spent after three misses; a resend waits 45 seconds.
5. A member token opens only `/api/account/` routes, and staff or campaign tokens do not open them; a member who stops being eligible is refused at their next request.
6. `/signin` sends a code from the phone tab, the code page verifies it and shows tries left, and a right code opens the account, or the chooser when the member also has a linked login; the chooser's other entries open the password sign-in.
7. The account shows the member card, the volunteer's details with a working change form, the empty tasks state, upcoming party events, and the data and privacy part; "Stop volunteering" keeps membership, "Leave the party" queues the withdrawal, and both end the session.
8. The directory lists only campaigns with an approved aspirant, a published and not hidden profile and access active, grace period or read-only; the profile's form accepts only wards in the campaign's area and is open only in active or grace period.
9. A campaign's volunteers are seen and changed only by its manager; the party register, its CSV and the dashboard hold party volunteers only; campaign withdrawal deletes the row and answers the same for any code.
10. Both test lanes pass; `backend/evals/` pass; existing tests pass unchanged except where this design changes volunteer fields, the join form or the sign-in page.

---

## 5. Not built in Release 5

What the designs show beyond the plan, left out on purpose: membership fee
and M-Pesa, national ID, date of birth, sex, leagues, party declaration,
member numbers, QR card, renewal, RSVP, branch officials, elections and
online primaries, nominations in the account, appeals, consent switches,
download my data, staff email sign-in and 2-step verification, voice-call
codes, password reset (`SysReset`), Nominees on the directory, campaign
events and news on the profile, volunteer tasks.

---

## 6. Decisions for Jeremy

Each has a recommendation; the design above is written with it.

| # | Question | Options | Recommended |
|---|---|---|---|
| 1 | Who can sign in by phone? The brief says volunteers; the designs say every member | (a) approved members who volunteer; (b) every approved member, with a non-volunteer's account showing the card, events and privacy part and a "Volunteer for events" form | (a): what the brief asks; (b) later is one rule and one form |
| 2 | Sign-in tabs. `SignIn.dc.html` groups "Members & campaigns" (phone code) against "Party staff" (email, password, 2-step) | (a) "Members" (phone code, member account only) and "Staff & campaigns" (today's username and password); a member with a linked login gets the chooser, whose other entries open the password sign-in; (b) the designs' grouping: candidates, managers and mobilizers move to phone codes too | (a): (b) changes how every campaign login signs in and needs each login's phone checked first, which is outside this release |
| 3 | Polling station. `Join.dc.html` asks every applicant for an optional polling centre; the sample requires it of volunteers | (a) asked only with the tick, and required there; members store no centre; (b) optional for every applicant and required with the tick, adding a centre column to `party_members` | (a): no member schema change |
| 4 | Who writes a candidate's profile? The designs say "maintained by the campaign, approved by the party" | (a) the manager writes and publishes; the superuser can hide it; (b) every change waits for party approval | (a): no approval queue to build; the party keeps a stop switch |
| 5 | Who appears in the directory? | (a) approved aspirants whose campaign published a profile; (b) every approved aspirant, profile or not | (a): a person is listed only once their campaign chooses to be |
| 6 | What does the "I'll volunteer" form ask? `Candidate.dc.html` asks for full name, phone, ward and consent | (a) the designs' fields with the name in two boxes, first and last, to match the volunteer columns; (b) the designs' single full-name box, split at the first space; (c) the sample's full fields | (a) |
| 7 | The profile's Events and News tabs. Campaign events exist (`models/event.py`) but have no public switch; campaign news does not exist | (a) not built; (b) Events lists the campaign's scheduled events, adding a "show on profile" switch per event | (a): keeps campaign data inside the campaign |
| 8 | Who sees campaign volunteers? | (a) the manager only (as approved this morning); (b) manager and candidate | (a) |

---

## 7. Risks

| # | Risk | Effect if missed | Mitigation |
|---|---|---|---|
| 1 | The code route shows who volunteers | A phone's place on the register leaks | One insert for any phone; the SMS sent after the answer; rubric 3 |
| 2 | A member token opens staff or campaign routes | A volunteer reaches party or campaign data | Separate table and scheme; rubric 5 |
| 3 | Six-digit codes guessed | Account taken | Three tries per code, five codes an hour per phone, ten requests an hour per device |
| 4 | A campaign volunteer reaches the party register or dashboard | Campaign data leaves the campaign | Every party read filters `campaign_id IS NULL`; rubric 9 |
| 5 | No SMS provider | Volunteers cannot sign in outside local work | Africa's Talking is wired (`SMS_PROVIDER=africastalking`); needs an account and a sender ID before live use |
| 6 | The rate limits are per API process (`services/ratelimit.py`) | Limits multiply with processes | One process today; recorded under Known gaps |
