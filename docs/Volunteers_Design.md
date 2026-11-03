# Release 5: Volunteers, Sign-in and Candidates

Technical design for volunteers, sign-in and the candidates pages as the UI
designs in `docs/party-platform-design/party-platform-design/` describe them
(`DESIGN_HANDOFF.md`; screens `Join`, `SignIn`, `SysCode`, `SysChooser`,
`MemberAccount`, `Candidates`, `Candidate`), keeping the registration fields of
the sample at `teamndiritumuriithi.co.ke/register`. The screens are visual and
behavioural reference rebuilt in our React stack. Where this design differs
from a screen, the screen changes to match (Jeremy, 3 November 2026).
It builds on `docs/Identity_Access_Design.md` (members, volunteers, the
`party_requests` queue) and `docs/Website_Design.md` (public site, website
editor, `/signin`).

Status: approved 3 November 2026, with the recommended answers to open points
A to C (section 6). The SMS code at sign-in is held back until an SMS provider
is set up (section 5).

Decisions taken by Jeremy on 3 November 2026:

1. **A volunteer is a party member.** The Join form's "Volunteer for events"
   tick opens the sample's fields: profession, the ten volunteer areas with
   Other, preferred contact and volunteer consent.
2. **Every approved member can sign in** to their member account, volunteer
   or not. Members vote in primaries and nominations, so they need accounts.
   A volunteer reaches their member account only, never the party console.
3. **One sign-in for everyone: email and password.** This replaces username
   and password for staff and campaign logins too. A 6-digit SMS code after
   the password comes last, once an SMS provider is chosen and set up; its
   design is kept in section 5.
4. **The Join form asks for email and a password**, both required, like the
   sample. Sign-in works once an officer approves the member.
5. **Polling station is required of every applicant** on the Join form. It is
   the registration centre, and it is stored on the member.
6. **Candidate profiles belong to the party website, not the CRM.** Candidates
   send their material and the party's website editor creates the profile.
   Party approval is the aspirant's approval at nomination. The CRM is a
   private paid product and publishes nothing to the website.
7. **The candidate profile's Events tab shows party events created on the
   website** and linked to that aspirant. Campaign events in the CRM stay
   private.
8. **The "I'll volunteer" form takes the sample's fields**, with first and
   last name boxes. Its volunteers go to that campaign's CRM, and only the
   campaign's manager sees them.

This replaces the design approved on the morning of 3 November: volunteers are
members again, everyone signs in with email and password, and the party `/volunteer`
page and the campaign `/volunteer/<code>` page are not built. It reverses
`Implementation_Plan.md` "Volunteers have no login".

Kept from Release 1: the volunteer consent box is separate from the membership
consent and its wording is stored (Data Protection Act, 2019); a public form
answers the same whatever the register holds; party and campaign data never
mix.

---

## 1. What exists today

| Piece | Where | What R5 does |
|---|---|---|
| Join with a volunteer part | `/join-party` (`pages/public/JoinParty.jsx`); `POST /api/party/join/`; `services/membership.py` `request_join` queues it, `_apply_join` applies it; `services/volunteers.py` `apply_part` writes the profile when the join adds or re-pends the member | Kept. The join gains first name and surname, required email, password and polling station; the volunteer part gains the sample's fields; the page is rebuilt on `Join.dc.html` |
| Members | `party_members`: `full_name`, `phone` (unique), `email` (optional), `ward_id`, status | Gains `registration_centre_id` |
| Volunteer profiles | `models/party.py` `VolunteerProfile`; R5-1 (`volunteer_register`) added `campaign_id`, own name, phone, email, ward, centre, profession, `interest_other`, and made `member_id` optional | See "R5-1: what stays and what reverts" |
| Profile follows the member | `follow_member`, `follow_withdrawal` | Kept unchanged |
| Officer register | `/party/volunteers`, `api/routers/party_volunteers.py`, CSV | New areas, profession and polling station; party rows only |
| Volunteer withdraw link | `/party/volunteer/withdraw/<code>`, queued | Kept |
| Sign-in | `POST /api/auth/login/` username and password; `auth_tokens`, one per `users` row; `users.kind` is `staff` or `campaign`; `api/deps.py` `get_current_user` lets a login with no campaign role straight through | Email and password for every login. A new login kind, `member` |
| Aspirants and campaigns | `aspirants` (member, seat, area, status, `campaign_id`); `api/routers/join.py` `_access` | The directory lists approved aspirants; the volunteer form needs a campaign with access |
| Party events | `party_posts` of kind event, `GET /api/party/posts/?kind=event`, edited in `pages/party/Website.jsx` (superuser) | An event can name aspirants; listed on the member account and on the aspirant's profile |

### R5-1: what stays and what reverts

R5-1 (`a8344f6`, migration `volunteer_register`) is not rolled back.

| R5-1 piece | Verdict | Why |
|---|---|---|
| `campaign_id` (NULL = party) | Stays | Candidate page volunteers are campaign rows |
| `first_name`, `last_name`, `phone`, `email`, `ward_id`, `registration_centre_id` | Stay | Campaign volunteers have no member row. A party row copies them from the join |
| `profession`, `profession_other`, `interest_other` | Stay | The sample's fields |
| Unique `(phone)` for party rows, `(campaign_id, phone)` | Stay | |
| `member_id` optional, to be dropped in R5-2 | **Reverts** | A party volunteer is a member. R5-2 keeps `member_id` and adds `CHECK ((campaign_id IS NULL) = (member_id IS NOT NULL))`: a party row has a member, a campaign row has none. `uq_volunteer_profiles_member_id` stays |
| Plan to remove the join's volunteer part and `apply_part` | **Reverts** | The tick on Join is the way in |

---

## 2. Design

### Principles

1. **One register, two owners.** A party volunteer is a member's profile
   (`member_id` set, `campaign_id` NULL). A campaign volunteer is campaign
   data (`campaign_id` set, no member): only that campaign's manager sees it,
   deleting the campaign deletes it, and the party register, CSV and
   dashboard never read it. Someone may be both, as two unlinked rows.
2. **Public forms do not show who is registered.** The join stays one queued
   insert. The candidate volunteer form answers the same for a new or a known
   phone. A wrong email and a wrong password get the same answer.
3. **A member login opens only the member account.** `get_current_user`
   refuses a `member` login, so no staff or campaign route lets one through;
   `/api/account/` routes use their own dependency.
4. **The website shows only what the party publishes.** Candidate profiles
   and their events are website content. Nothing is read from a campaign's
   CRM for the website.

### Data model

Three revisions, in this order: `volunteer_areas` (R5-2), `member_logins`
(R5-3), `candidate_profiles` (R5-6).

#### `party_members` and `volunteer_profiles` (R5-2, `volunteer_areas`)

| Change | Rule |
|---|---|
| `party_members.registration_centre_id` | FK `registration_centres` NULL (members from before R5 lack it); the join requires it and it must lie in the member's ward |
| `party_members.first_name` | `varchar(75)` NULL; set from the join (older members lack it, and the account then greets the first word of `full_name`) |
| `volunteer_profiles.member_id` | Kept; `CHECK ((campaign_id IS NULL) = (member_id IS NOT NULL))` |
| `volunteer_profiles.interests` | JSON list of `VolunteerArea` values; at least one |
| Old interests | Mapped: `mobilisation` → `mobilising_voters`; `social_media`, `fundraising` as they are; the rest → `other` with their label in `interest_other` (no live data; this keeps the dev database whole) |

`VolunteerArea` (replaces `VolunteerInterest`): `fundraising`,
`door_to_door`, `mobilising_voters`, `social_media`, `recruiting`,
`materials`, `data_collection`, `community_listening`, `barazas`, `other`;
labels as on the sample ("Holding Barazas & Household Meetings").

#### `users` (R5-3, `member_logins`)

| Change | Rule |
|---|---|
| `UserKind.MEMBER` | A member's own login: no campaign role, no party office, `party_member_id` set. The kind CHECK becomes: `staff` and `member` have no role, `campaign` has one. Deleting a member sets every linked login's `party_member_id` to NULL; a member login left so can no longer sign in |
| `users.email` | Unique (case-folded) where not empty; the sign-in name. `username` stays for the CLI |

#### `candidate_profiles` and event links (R5-6, `candidate_profiles`)

| Column | Rule |
|---|---|
| `aspirant_id` | PK, FK `aspirants` ON DELETE CASCADE |
| `photo_url` | `https://` URL or `''`, as party leaders' photos |
| `slogan` | `varchar(120)` |
| `bio` | text, at most 2,000 characters |
| `priorities` | JSON list of up to 3 `{title, text}`, title ≤ 80, text ≤ 300 |
| `office_address`, `office_phone`, `office_email` | optional |
| `published` | bool, default false |

`party_post_aspirants` (new): `(post_id, aspirant_id)`, both FK ON DELETE
CASCADE. An event post may name any number of aspirants.

### Joining (R5-2, R5-4)

`POST /api/party/join/` changes:

| Field | Rule |
|---|---|
| `first_name`, `surname` | replace `full_name`; stored as `party_members.first_name` and `full_name = "first surname"`, and on a volunteer row as typed |
| `email` | required |
| `password` | required, 8 to 128 characters as for logins made by the superuser (`schemas/admin.py`); hashed before it is queued, so `party_requests` never holds it in clear |
| `registration_centre` | required; must lie in `ward` |
| `volunteer.profession`, `profession_other` | required with the tick; text required when `other` |
| `volunteer.areas`, `area_other` | one or more `VolunteerArea`, no repeats; text required when `other` |
| `volunteer.preferred_contact`, `consent_given` | kept |

Centres of a ward come from `GET /api/party/places/?ward=<id>` (added to the
existing route).

When a queued join adds or re-pends a member, `_apply_join` also writes the
member's login: a `users` row of kind `member` with the member's email, phone,
name and password hash, created or refreshed. When the email already belongs
to a login linked to the same member, no second login is made and that login's
chooser gives My membership. When it belongs to an unrelated login, the member
is still added but gets no member login, and the officer's member list shows
"No sign-in: email in use"; the public answer is unchanged (decision B).

### Sign-in for everyone (R5-3, R5-5)

| Route | Does |
|---|---|
| `POST /api/auth/login/` `{email, password}` | Replaces `{username, password}`. Wrong email or password: today's 400 "Unable to log in with the provided credentials.". Right: `{token, user}` as today. 10 tries an hour per device |
| `POST /api/auth/logout/` | Unchanged |

**A member login can sign in** only while its member is `approved`;
otherwise it gets the same 400 as a wrong password. Every `/api/account/`
request rechecks this, so suspension or withdrawal ends the session at the
next request.

**The demo and existing logins:**
- `campaign-crm demo` gives every login it makes an email (`<username>@demo.pamoja.test`), and adds one approved member with a volunteer profile and a member login.
- A new command, `campaign-crm set-email -u <username> --email <e>`, fills the email of logins made before R5 (`r2check`, `teuzi`, `pesa`, the Achieng logins).
- Signing in locally: email and the login's password (`Mzigo-Demo-2026` for the local logins today; `campaign-crm demo` uses `DEFAULT_USER_PASSWORD`).

### Where a login goes after sign-in (R5-5)

| Login | Goes to |
|---|---|
| `member` | `/account` |
| `staff` or `campaign` with no approved member linked | Where it goes today |
| `staff` or `campaign` linked (`party_member_id`) to an approved member | "Where to?" (`SysChooser.dc.html`): its own area and My membership |

### The member's account (R5-3, R5-5)

Built on `MemberAccount.dc.html`, with only what our data holds. Tasks are
deferred in `Implementation_Plan.md`, so the tasks area is an empty state.
Account routes take a `member` login, or a staff or campaign login linked to
an approved member, and always act on that one member.

| Part | Shows | Route |
|---|---|---|
| Header | "Habari, <first name>", Public site, Sign out | |
| Member card | Full name; branch (ward, county); polling station; member since (month and year of `party_members.created_at`); status pill | `GET /api/account/` |
| Tab: Volunteering | A volunteer sees status (Interested, Active, Inactive), areas, profession, preferred contact; "Change my volunteer details"; "My volunteer tasks" with "No tasks yet. Your branch will contact you when there is something to do."; and "Volunteering for a candidate's campaign happens on their profile page", linking to `/candidates`. A member who does not volunteer sees "Volunteer for events" with the same fields and consent | `GET /api/account/`, `PUT /api/account/volunteer/` |
| Tab: Party events | Upcoming published party events, soonest first, each linking to its page | `GET /api/party/posts/?kind=event` (existing) |
| Tab: My data & privacy | Name, masked phone, email, ward, polling station; the membership and volunteer consents with wording and dates; "Stop volunteering" (withdraws the volunteer profile, keeps membership); "Leave the party" (queues the same withdrawal as the member's link and ends the session); to correct name, phone, ward or polling station, the party office's contact | `POST /api/account/volunteer/stop/`, `POST /api/account/leave/` |

A member's own changes are audited as `volunteer.self_update` (field names
only) and `volunteer.status`, with the member's login as the actor. Becoming a volunteer from
the account copies the member's details onto the profile as `apply_part`
does. "Leave the party" uses `request_withdraw` with the member's withdraw
code, so `follow_withdrawal` and the officer flow are unchanged.

### Candidates on the website (R5-6, R5-7)

The website editor creates each profile from what the candidate sends. The
website editor is the superuser today, as for the rest of the website in R4
(decision A). Nothing on a profile is read from a campaign's CRM.

| Route | Does |
|---|---|
| `GET /api/candidates/?seat=&county=&q=` | Public. Listed aspirants: name, seat, area, county, photo, slogan, and a slug `<seat>-<area-name>-<short id>` |
| `GET /api/candidates/{slug}/` | Public. The above plus bio, priorities, office contacts, upcoming published party events naming the aspirant, and whether volunteering is open with the area's wards |
| `POST /api/candidates/{slug}/volunteer/` | Public. First and last name, email, phone, ward and polling station (inside the seat's area), profession (Other with text), one or more areas (Other with text), preferred contact, consent. Writes a campaign volunteer row; a known phone is left as it is; the answer and a withdrawal link are the same either way. 20 an hour per device |
| `POST /api/candidates/volunteer/withdraw/{code}/` | Deletes the campaign volunteer; the same answer for any code |
| `GET`, `PUT /api/admin/party/candidates/{aspirant_id}/profile/` | Superuser: write and publish an approved aspirant's profile |
| `PUT /api/admin/party/posts/{id}/aspirants/` | Superuser: the aspirants an event names (beside the existing `/api/admin/party/posts/` routes) |
| `GET /api/campaigns/{id}/volunteers/`, `PATCH .../volunteers/{vid}/` | The campaign's manager lists (search, ward, status) and moves a volunteer to active or inactive, with notes |

**Listed** when the aspirant is `approved` and its profile is `published`.
**Volunteering open** when listed and the aspirant has a campaign whose access
is active or grace period. Otherwise the profile shows no form. This is the one
thing the website checks about a campaign: a yes or no, no CRM content
(decision C).

The directory shows one list ("Aspirants") with filters for seat, county and a
name or area search; the design's Nominees tab waits for primaries. The
profile page shows About, Priorities, Events (party events naming the
aspirant), the "Support <first name>" form and the campaign office. News is
not built.

The campaign volunteer routes join `CAMPAIGN_READS` / writes in
`tests/test_route_guards.py`; read-only and locked campaigns refuse the writes.

### Frontend

| Where | Change |
|---|---|
| `pages/public/JoinParty.jsx` | Rebuilt on `Join.dc.html`: three steps (Your details with email and password; Your branch with a required polling station and the "Volunteer for events" tick opening the sample's fields; Consent) and the done screen with withdrawal links. No national ID, date of birth, sex, leagues, declaration or fee |
| `components/Login.jsx` (shown by `SignInPage` in `src/Gate.jsx`, `/signin`) | Rebuilt on `SignIn.dc.html` as one form: email, password, Sign in. No tabs |
| `pages/public/Chooser.jsx` (`/signin/where`) | `SysChooser.dc.html`, for linked logins only |
| `pages/member/Account.jsx` (`/account`) | `MemberAccount.dc.html` with the parts above |
| `pages/public/Candidates.jsx` (`/candidates`), `Candidate.jsx` (`/candidates/:slug`) | `Candidates.dc.html`, `Candidate.dc.html` as above |
| `/candidates/volunteer/withdraw/:code` | Campaign volunteer withdrawal |
| `components/PublicLayout.jsx` | Menu gains Candidates |
| `pages/party/Website.jsx` | Candidates tab: approved aspirants, profile form, Publish; an event's form picks the aspirants it names |
| `pages/party/Volunteers.jsx`, `Dashboard.jsx`, `helpers.js` | New areas, profession and polling station |
| `pages/campaign/Volunteers.jsx`, `helpers.js` | Manager: the campaign's volunteer list |

---

## 3. Tickets

Migrations run one at a time, in ticket order (R5-2, R5-3, R5-6). A route
enters `contracts/frontend-api.json` in the frontend ticket that first calls
it. Each ticket gets one cold critic judged on its text and section 4 only.

**R5-1 Volunteer register schema** (done, `a8344f6`).

**R5-2 Join and volunteer areas** (backend; done with R5-4, migration head `volunteer_areas`)
- Files: revision `volunteer_areas`; `models/enums.py` (`VolunteerArea`), `models/party.py`; `schemas/party.py`, `schemas/dashboard.py`; `services/membership.py`, `services/volunteers.py`, `services/dashboard.py`; `api/routers/party.py` (join, centres of a ward), `api/routers/party_volunteers.py`; `docs/party-platform-design/party-platform-design/screens/Join.dc.html` (polling centre required, email required, password field); tests; `backend/evals/test_inbox_constant_work.py`, whose join payload and `VOLUNTEER_PART` change.
- Tests: a join stores first name and surname, email and polling station on the member; with the tick, the volunteer's profession and areas; a centre outside the ward, a missing email or password, and `other` without text are refused; the queued payload holds no clear password; a party row without a member and a campaign row with one fail at the database; the register, CSV and dashboard leave campaign rows out.

**R5-3 Email sign-in for everyone and the account API** (backend, with the sign-in form's email field; done, migration head `member_logins`)
- Files: revision `member_logins`; `models/user.py`, `models/enums.py` (`UserKind.MEMBER`); `schemas/auth.py`; `services/accounts.py`, `services/membership.py` (member login on apply); `api/deps.py`; `api/routers/auth.py`, `api/routers/account.py`, `api/routers/party_members.py` and `schemas/party.py` `MemberRead` (`has_login`); `cli.py` (`set-email`); `seed/demo.py`; tests.
- Tests: a login signs in with email and password and no longer with a username; a pending member's right password gets the wrong-password answer; a member login gets 403 from every staff and campaign route, and suspending the member makes its next account request 401; a linked campaign login reads its member's account; applying a join makes a member login, and an email already in use leaves the member without one.

**R5-4 Join page and party volunteer pages** (frontend; done with R5-2, so the join form and its API change together)
- Files: `pages/public/JoinParty.jsx`, `pages/party/Volunteers.jsx`, `Dashboard.jsx`, `Members.jsx` ("No sign-in: email in use"), `helpers.js`, `api/hooks`, contract, tests.
- Tests: the polling station is required and loads for the chosen ward; the tick shows and requires the volunteer fields; the request carries what the route takes; the officer register filters by the new areas.

**R5-5 Sign-in and account pages** (frontend; depends R5-3; done)
- Files: `components/Login.jsx`, `Chooser.jsx`, `pages/member/Account.jsx`, `Gate.jsx`, `App.jsx`, `api/hooks`, `store`, contract, tests; `screens/SignIn.dc.html` (one email and password form, no tabs).
- Also: the login forms that create logins (new campaign, manager, mobilizer) require an email, since a login without one cannot sign in.
- Tests: the form sends email and password; a member login opens the account, a linked login the chooser, others the console; the account shows the card, the volunteer details or the volunteer form, and the empty tasks state; a 401 returns to `/signin`.

**R5-6 Candidate profiles and campaign volunteers API** (backend; depends R5-3)
- Files: revision `candidate_profiles`; `models/content.py`; `schemas/candidates.py`; `services/candidates.py`, `services/content.py`, `services/volunteers.py`; `api/routers/candidates.py`, `api/routers/admin.py` (profiles, event aspirants), `api/routers/campaigns.py`; `tests/test_route_guards.py`; tests.
- Tests: only approved aspirants with a published profile appear; the profile lists published upcoming party events naming the aspirant and no campaign event; the form is absent without a campaign and closed in read-only or locked; a ward or centre outside the seat's area is refused; a known phone gets the same answer and no second row; the manager sees only their campaign's volunteers, another campaign's id answers 404, and the candidate and a mobilizer get 403; withdrawal deletes and answers the same for any code; deleting the campaign deletes its volunteers.

**R5-7 Candidates pages, website editor and manager page** (frontend; depends R5-6)
- Files: `screens/Candidate.dc.html` (the support form takes the sample's fields with first and last name), `Candidates.jsx`, `Candidate.jsx`, the withdraw page, `pages/party/Website.jsx`, `pages/campaign/Volunteers.jsx`, campaign `helpers.js` (manager menu), `PublicLayout.jsx`, `Gate.jsx`, `api/hooks`, contract, tests.
- Tests: filters narrow the list; the profile's form offers only the seat's wards and is hidden without an open campaign; the editor publishes a profile and links an event; the manager lists volunteers.

**R5-8 Integration** (lead)
- Both test lanes; `backend/evals/`; demo seed (a published profile with a linked event, a volunteer member who can sign in); `docs/SYSTEM.md`; one release critic against section 4 only.

---

## 4. Rubric for the critics (frozen once approved)

A critic judges these points and nothing wider. A finding outside them is
listed as non-blocking under Known gaps.

1. The Join form requires first name, surname, phone, email, password, ward and a polling station within that ward. The tick adds and requires profession (Other with text), one or more of the ten areas (Other with text), preferred contact and volunteer consent. The result is a pending member with those details, a volunteer profile when ticked, and a member login with the password, which no queued row holds in clear.
2. A party volunteer row always has a member and a campaign volunteer row never does, enforced by the database.
3. Every login signs in with email and password, and a username no longer signs in; the demo logins and `set-email` give every local login an email.
4. A wrong email and a wrong password get the same answer, and so does a member who is not approved.
5. A member login signs in only while its member is approved, opens only `/api/account/` routes, and is refused at its next request once the member stops being approved.
6. After sign-in, a member login opens its account; a linked staff or campaign login gets the chooser; others go where they go today.
7. The account shows the member card, the volunteer part (details with a working change form, or the volunteer form for a non-volunteer), the empty tasks state, upcoming party events, and the data and privacy part; "Stop volunteering" keeps membership and "Leave the party" queues the withdrawal and ends the session.
8. The directory lists only approved aspirants with a published profile; a profile shows party events naming it and never a campaign event; its volunteer form appears only for a campaign in active or grace period and accepts only places inside the seat's area.
9. A candidate profile is written and published only by the website editor, and no field on it comes from a campaign's CRM. The "I'll volunteer" form asks for and requires first name, last name, email, phone, ward, polling station, profession (Other with text), one or more of the ten areas (Other with text), preferred contact and consent.
10. `Join.dc.html`, `SignIn.dc.html` and `Candidate.dc.html` show what this design builds: a required polling centre, email and password on Join; one sign-in form; the full volunteer form on the profile.
11. A campaign's volunteers are seen and changed only by its manager; the party register, its CSV and the dashboard hold party volunteers only; campaign withdrawal deletes the row and answers the same for any code.
12. Both test lanes pass; `backend/evals/` pass; existing tests pass unchanged except where this design changes volunteer fields, the join form or sign-in.

---

## 5. Not built in Release 5

Left out on purpose: membership fee and M-Pesa, national ID, date of birth,
sex, leagues, party declaration, member numbers, QR card, renewal, RSVP,
branch officials, elections and online primaries, nominations in the account,
appeals, consent switches, download my data, voice-call codes, password reset
(`SysReset`), Nominees on the directory, News on the profile, volunteer tasks.

### Later: SMS code at sign-in (R5-9, after everything else)

Held back by Jeremy on 3 November 2026 until an SMS provider is chosen and set
up. Kept here so the work is ready:

- After a right email and password, `POST /api/auth/login/` writes a code, sends it by SMS to `users.phone` and answers `{challenge, phone_hint}` with no token; `POST /api/auth/verify/` `{challenge, code}` gives the token; `POST /api/auth/resend/` waits 45 seconds.
- `sign_in_codes`: `id` (the challenge), `user_id` unique, `code_hash` (HMAC-SHA256 with `SECRET_KEY`), `expires_at` (10 minutes), `tries_left` (3), `created_at`.
- `ConsoleSMSProvider` logs the message text, so the code shows in the API's terminal locally.
- Screens: `SysCode.dc.html` as `pages/public/SignInCode.jsx`; a login without a phone is told to ask the party office.
- A password reset by SMS code (`SysReset.dc.html`) fits on the same table.

---

## 6. Decisions on the open points

Taken by Jeremy on 3 November 2026, all as recommended.

| # | Question | Decision |
|---|---|---|
| A | Who is "the website manager" who creates candidate profiles? | The superuser, who edits the whole website today. A "website editor" office can come later as one enum value and a guard |
| B | A member's email is already used by another login | If that login is linked to the same member (`users.party_member_id`), its chooser gives My membership; an unrelated clash leaves the member without a login, shown to the officer as "No sign-in: email in use" |
| C | How the profile's volunteer form knows the campaign can take volunteers | The website reads only the campaign's access state, and shows the form while it is active or in grace period |

---

## 7. Risks

| # | Risk | Effect if missed | Mitigation |
|---|---|---|---|
| 1 | A member login reaches staff or campaign routes | A member reaches party or campaign data | `get_current_user` refuses kind `member`; the route-guard test walks every route; rubric 5 |
| 2 | Passwords alone until the SMS code step lands | A guessed or reused password opens a login | 10 tries an hour per device; R5-9 adds the code |
| 3 | Logins made before R5 have no email | They cannot sign in | `set-email` and the demo seed fill them; `reset-password` works from the CLI; rubric 3 |
| 4 | A campaign volunteer reaches the party register or dashboard | Campaign data leaves the campaign | Every party read filters `campaign_id IS NULL`; rubric 11 |
| 5 | The rate limits are per API process (`services/ratelimit.py`) | Limits multiply with processes | One process today; recorded under Known gaps |

---

## 8. The updated designs (3 November 2026, afternoon)

Jeremy updated the designs (`9778aac`): a shared `SiteHeader` and `SiteFooter`,
website patterns (`WebPatterns`), a homepage with a photo carousel and colour
bands, a news layout, and a CRM top bar (`CrmTopBar`) with page headers.

Status: approved 3 November 2026 with Jeremy's answers to P1 to P8 below.

Decisions taken by Jeremy:

1. **Party branding, not "Mzigo".** The demo party is "Pamoja Party". Sign-in,
   console, admin, onboarding and the campaign shell show the party's name and
   logo from the website settings instead of the hard-coded MZIGO·CRM. "Powered
   by" stays off until the product has a name. Fly app, Neon project and package
   names stay (a deploy change).
2. **All of the new patterns are Release 5**: the shared header and footer, the
   homepage, the news, events and about pages, and the party CRM's top bar and
   page headers.

### Answers to the open points

| # | Point | Decision |
|---|---|---|
| P1 | County branches | Built. The party that buys the system enters its branches; the demo seed fills dummy branches for every county. Counties link, "Find your branch" and the branch page are shown |
| P2 | Contribute | Built for the demo. Payments will go through Paystack once a party buys the system; until then the Contribute page takes an amount and details and answers that this is a demo and no money moved. Nothing is charged or stored as a payment |
| P3 | EN / SW | Hidden until Kiswahili copy exists |
| P4 | Results and "Vie with us" | Built for the demo: a Results page reading results the website editor enters (the seed adds demo results, marked as such), and a "Vie with us" page with the steps and the party office's contacts |
| P5 | News extras (Most read, Watch, trending tags) | Left out |
| P6 | Events map and RSVP | Left out; events by month with a county filter |
| P7 | CRM scope switcher | Left out |
| P8 | Campaign CRM | Restyled, interface included, as a later step: Jeremy will add how its pages should look. Until then it takes the new tokens and party branding only |

### New tickets

**R5-10 Branding and design tokens** (frontend and seed)
- Party name and logo replace MZIGO in `components/Login.jsx`, `App.jsx`, `components/Admin.jsx`, `components/Onboarding.jsx`, `index.html`; the demo party in `seed/site.py` is "Pamoja Party"; demo emails become `<username>@demo.pamoja.test` (seed, tests, and local logins through `set-email`); `index.css` takes the handoff's tokens (grounds, ink, muted, borders, pills, Bricolage Grotesque and Public Sans, two-layer card shadow, radii).
- Tests: the sign-in page and console show the party's name from `GET /api/party/` and no "MZIGO"; the seed names Pamoja Party.

**R5-11 Site header, footer and newsletter** (backend and frontend; depends R5-10; done, migration head `subscribers`)
- Party settings gain `registration_number`, `slogan`, `privacy_notice` (text) and `privacy_notice_version`. New `subscribers` (phone or email, consent wording, notice version, date, unsubscribe code) with `POST /api/party/subscribe/` (the same answer for a known or new contact, rate limited) and an unsubscribe link. `components/SiteHeader.jsx` (sticky frosted bar, utility line with registration number and hotline, logo and slogan, nav with the current page as a pill, Join, Contribute, Sign in or "My account / Sign out"; no EN/SW), `components/SiteFooter.jsx` (sign-up with consent wording, link columns, social, legal: privacy notice page, data protection line), breadcrumbs, the phone action bar; `PublicLayout.jsx` uses them; `/privacy` page.
- Contribute (P2): `/contribute` page (amount, name, phone, consent) and `POST /api/party/contribute/`, which answers that this is a demo and no money moved, and stores nothing; `PAYMENTS_PROVIDER=demo` names the mode so Paystack can take its place.
- Tests: a sign-up stores its consent and notice version and answers the same twice; unsubscribe removes it; the header marks the current page and swaps Sign in for My account when signed in; the contribute route stores nothing and says it is a demo.
- Known gap: a contact already signed up keeps its first row and code, so the unsubscribe link a repeat sign-up hands back changes nothing; the first link still works. The answer stays the same for a known or new contact. Nothing sends the link by SMS or email yet.

**R5-12 Homepage** (backend and frontend; depends R5-11)
- Website content gains hero slides (up to 5: image URL, kicker, headline, line, button) and agenda issues (title, summary, what we will do, why it matters, order); `pages/public/Home.jsx` rebuilt on `PartyHome.dc.html`: carousel (6-second rotation, previous, next, dots, Pause, stops for reduced motion), agenda, news (lead and three), upcoming events, candidates (after R5-6, else hidden), leadership, "Three ways to take part" (P2, P4), sign-up band; `pages/public/Issue.jsx` (`/issues/:id`) on `PubIssue.dc.html`; the website editor manages slides and issues.
- Tests: the carousel moves, pauses and offers each slide; an unpublished slide or issue is not public; the editor saves slides in order.

**R5-13 News, article, events and about pages** (backend and frontend; depends R5-11)
- Posts gain `label` (Statement, News, Opinion), `place`, `author`, `author_photo_url`, and for statements `reference` and `pdf_url`; event posts gain an optional `county_id` (the county filter and branch pages use it); read time is computed. `News.jsx` on `News.dc.html` (lead with three beside it, Latest rail, Opinion, Official statements); `Post.jsx` on `PubArticle.dc.html` (official record box for statements, read next); `Events.jsx` on `Events.dc.html` (by month, county filter; P6); `About.jsx` on `PubAbout.dc.html` (what we believe, leadership, how the party is run, documents as website content: title and https link).
- Tests: a statement shows its reference and PDF; the county filter narrows events; documents list only published ones.

**R5-14 Party CRM top bar and page headers** (backend and frontend; depends R5-10)
- `components/CrmTopBar.jsx` on every party console page: breadcrumb, search (Ctrl K) over members and aspirants (`GET /api/party/search/?q=`, officers see only what their roles allow), notifications with counts (pending applications, submitted aspirants, held payments) linking to their pages, help, the signed-in person and role; each console page gets the frosted page header with its actions on the right.
- Tests: search returns only what the caller's role may see; a membership officer gets no aspirant results; the notification count matches pending applications.

**R5-15 County branches** (backend and frontend; depends R5-11; done, migration head `branches`; the console form also sets the next meeting and Published, which nothing else sets; events in the county wait for R5-13)
- `branches`: one per county (`county_id` unique), chairperson, secretary, office address, phone, email, next meeting (date, venue), published. Superuser edits them in the console (`pages/party/Branches.jsx` on `CrmBranches.dc.html`, officials and office only). Public `GET /api/party/branches/` and `/branches/{county_id}/`; `pages/public/Branches.jsx` (`/counties`) and `Branch.jsx` (`/counties/:id`) on `PubBranch.dc.html`: officials, office, next meeting, sub-branches as the county's constituencies and wards, upcoming party events in the county (after R5-13). The homepage's "Find your branch" card and band (R5-12) read them. The demo seed fills a dummy branch for every county.
- Tests: an unpublished branch is not public; only the superuser edits; the seed gives each county one branch.

**R5-16 Demo results and "Vie with us"** (backend and frontend; depends R5-11)
- `primary_results` as website content: seat, area name, candidate name, votes, declared date, published. `GET /api/party/results/`; `pages/public/Results.jsx` (`/results`) on `PubResults.dc.html` without the receipt checker; the editor enters results; the seed adds demo results marked "Demo results". `pages/public/Vie.jsx` (`/vie`): the steps to become an aspirant from a website setting, and the party office's contacts.
- Tests: only published results show, grouped by seat; the page says "Demo results" when the seed made them.

**Order**: R5-3 (done), R5-10, R5-11, R5-5 (sign-in and account on the new shell), R5-15, R5-12, R5-13, R5-16, R5-6, R5-7, R5-14, R5-8; R5-9 last. The campaign CRM restyle (P8) follows when Jeremy adds its page designs.

### New rubric points (frozen once approved)

13. No page says "Mzigo"; every header shows the party's name and logo from the website settings, and the demo party is Pamoja Party.
14. Every public page uses the one `SiteHeader` and `SiteFooter`, with the current page marked; the footer's sign-up stores consent wording, notice version and date, answers the same for a known contact, and can be undone by its link.
15. The homepage carousel rotates every 6 seconds, has previous, next, dots and Pause, and stops for reduced motion; slides and issues are website content only the editor changes.
16. News, article, events and about pages follow their screens with the data this design adds; nothing from P5, and no map or RSVP, is shown.
17. Every party console page has the top bar; search and notifications show only what the caller's roles may see.
18. Every page works at phone width with touch targets of 44px or more.
19. Each county has at most one branch; published branches show their officials, office, next meeting and the county's wards; only the superuser edits them.
20. The Contribute page charges nothing and stores nothing, and says so.
21. Results show only published entries, and demo results say they are demo.
