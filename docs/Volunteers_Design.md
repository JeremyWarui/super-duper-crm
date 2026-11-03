# Release 5: Volunteer Registration

Technical design for volunteer registration modelled on the sample at
`teamndiritumuriithi.co.ke/register`. It builds on
`docs/Identity_Access_Design.md` (Release 1 volunteers) and
`docs/Website_Design.md`, and keeps their principles: party and campaign data
never mix, public forms answer the same whatever the register holds, and
consent is the person's own.

Status: approved 3 November 2026, with the five choices in the reply to the draft (no member link, the sign-up link opens the volunteer page, manager only, campaign withdrawal deletes, polling station and email required).

Decisions taken by Jeremy on 3 November 2026:

1. **Both the party and each campaign get a volunteer page.** The party's page
   covers the whole country; a campaign's page offers only its seat's area,
   like the sample's Laikipia-only list.
2. **A volunteer need not be a party member.** Volunteering has its own form.
3. **Volunteers get no login.** They register with consent and get a private
   withdrawal link, as today.
4. **The form takes the sample's fields:** first and last name, phone, email
   (required), constituency, ward and polling station, profession, and the
   sample's ten volunteer areas.

Kept from today, unlike the sample: the consent box is required and its
wording is stored with the volunteer (Data Protection Act, 2019). The sample
has no consent text and asks for a password; we ask for neither a password
nor an account.

---

## 1. What exists today

| Piece | Where | What R5 changes |
|---|---|---|
| Volunteer profiles | `models/party.py` `VolunteerProfile`: one per party member (`member_id` unique), interests (7), preferred contact, consent, withdraw code, status interested/active/inactive/withdrawn | Becomes the one volunteer register for the party and for campaigns, with its own personal details |
| Joining with a volunteer part | `/join-party` form section; `services/membership.py` `request_join` queues it; `services/volunteers.py` `apply_part` | The section is replaced by a link to the new volunteer page |
| Profile follows the member | `services/volunteers.py` `follow_member`, `follow_withdrawal` | Removed: a volunteer is no longer tied to a member |
| Officer register | `/party/volunteers`, `api/routers/party_volunteers.py`, CSV export | Shows the new fields; filters by place, area and status |
| Party withdraw link | `/party/volunteer/withdraw/<code>`, queued | Unchanged |
| Campaign sign-up link | `campaigns.signup_code`, `signups_open`; `api/routers/join.py` `_link`, open only while the aspirant is approved and access is active or grace | The campaign's volunteer page uses the same code and the same open rule |
| Places | `GET /api/party/places/` (counties, constituencies, wards); 27,273 registration centres loaded | Adds a ward's centres; "polling station" on screen is our registration centre |
| Dashboard | `services/dashboard.py` active volunteers by county and interest | Counts party volunteers by their own ward and the new areas |

---

## 2. Design

### Principles

1. **One register, two owners.** A volunteer row belongs to the party
   (`campaign_id` NULL) or to one campaign. A campaign's volunteers are
   campaign data: only that campaign sees them, and deleting the campaign
   deletes them. The party never reads a campaign's volunteers, and the
   dashboard counts party volunteers only.
2. **The party form answers like the join form.** A party volunteer
   registration is queued (`party_requests`), one insert whatever the register
   holds, so neither the answer nor its timing shows who is registered.
3. **A campaign's form answers like its supporter sign-up.** Written at once,
   the same answer and a withdrawal code for a new or a known phone.

### Data model

One revision, `volunteer_register`, on top of `public_content`.

#### `volunteer_profiles` (changed)

| Column | Rule |
|---|---|
| `member_id` | dropped, with `uq_volunteer_profiles_member_id` |
| `campaign_id` | UUID NULL, FK `campaigns` ON DELETE CASCADE; NULL for the party |
| `first_name`, `last_name` | `varchar(75)`, required |
| `phone` | `varchar(20)`, required, normalised Kenyan mobile |
| `email` | `varchar(254)` NULL; the form requires it, rows moved from Release 1 may lack it |
| `ward_id` | FK `wards`, required |
| `registration_centre_id` | FK `registration_centres` NULL; the form requires it, moved rows lack it. Must lie in `ward_id` (checked by the service) |
| `profession` | `farmer, teacher, business, student, other` NULL (moved rows) |
| `profession_other` | `varchar(100)`, default `''`; required when `profession = other` |
| `interests` | JSON list of the new `VolunteerArea` values, at least one |
| `interest_other` | `varchar(100)`, default `''`; required when `other` is chosen |
| `preferred_contact` | kept |
| `status`, `availability_notes`, `consent_wording`, `consent_at`, `withdraw_code` | kept |

Unique: `(phone)` where `campaign_id IS NULL`, and `(campaign_id, phone)`.
Index on `(campaign_id, status)` and `ward_id`.

`VolunteerArea` (replaces `VolunteerInterest`): `fundraising`,
`door_to_door`, `mobilising_voters`, `social_media`, `recruiting`,
`materials`, `data_collection`, `community_listening`, `barazas`, `other`;
labels as on the sample ("Holding Barazas & Household Meetings").

Moving Release 1 rows: each profile takes its member's name (first word as
first name, the rest as last name), phone, email and ward. Old interests map
`mobilisation` → `mobilising_voters`, `social_media` and `fundraising` as they
are; the rest become `other` with their old label in `interest_other`. There
is no live data yet, so this keeps the dev database whole rather than
preserving meaning.

### Public routes (no login)

| Route | Does |
|---|---|
| `GET /api/party/places/?ward=<id>` | The ward's registration centres (adds to the existing route) |
| `POST /api/party/volunteer/` | Queue a party volunteer registration; answers the thank-you and a withdrawal code, rate limited 20 an hour per device |
| `GET /api/join/{code}/volunteer/` | The campaign's name, seat, area and whether volunteering is open |
| `GET /api/join/{code}/volunteer/places/?constituency=&ward=` | Constituencies, wards and centres inside the campaign's area only |
| `POST /api/join/{code}/volunteer/` | Register a campaign volunteer, open on the same rule as the sign-up link |
| `POST /api/join/volunteer/withdraw/{code}/` | Delete a campaign volunteer by their code; the same answer for any code |

The party form's queued request: a known phone whose volunteer is not
withdrawn is left as it is; a withdrawn one returns to interested with the new
details; a new phone adds an interested volunteer. A campaign registration
leaves a known phone as it is, like a supporter. The existing party withdraw
route keeps working.

### Signed-in routes

| Route | Who |
|---|---|
| `/api/party/volunteers/` list, update, `export.csv` | membership officer and superuser, as today; party volunteers only |
| `GET /api/campaigns/{id}/volunteers/` (search, place, area, status), `PATCH .../volunteers/{vid}/` (active or inactive, notes) | the campaign's manager |

The new campaign `GET` joins `CAMPAIGN_READS` in `test_route_guards.py`; the
`PATCH` is a write, so read-only and locked campaigns refuse it as usual.
Officer and manager changes are audited as `volunteer.status` and
`volunteer.notes` with ids and statuses only.

### Frontend

| Where | Change |
|---|---|
| `pages/public/Volunteer.jsx` (new), route `/volunteer` | The party's form inside `PublicLayout`, laid out like the sample: Personal information (first name, last name, email, phone), Location (county, constituency, ward, polling station), Profession, Volunteer interest (tick one or more, Other opens a text box), preferred contact, consent, Register. The done screen shows the withdrawal link |
| `components/PublicLayout.jsx` | Menu gets Volunteer |
| `pages/public/JoinParty.jsx` | The volunteer section becomes a link to `/volunteer` |
| `pages/public/CampaignVolunteer.jsx` (new), route `/volunteer/:code` | The same form in the campaign's name, places limited to its area; an MCA campaign shows its ward fixed and asks only for the polling station |
| `/volunteer/withdraw/:code` (new) | Campaign volunteer withdrawal |
| `pages/party/Volunteers.jsx` | New columns and filters; no member status |
| `pages/campaign/Volunteers.jsx` (new) | Manager: list, filters, active or inactive, notes |
| `pages/campaign/CampaignLinkModal.jsx` | Shows the volunteer link next to the sign-up link, with Copy and WhatsApp |

---

## 3. Tickets

The migration runs first and alone (R5-1). A route enters
`contracts/frontend-api.json` in the frontend ticket that first calls it.

**R5-1 Volunteer register schema** (schema)
- Files: `models/party.py`, `models/enums.py` (`VolunteerArea`, `Profession`), new revision `volunteer_register`, `tests/test_models.py`, `tests/test_migrations.py` if it lists revisions.
- Tests: two party volunteers with one phone fail at the database; the same phone on two campaigns and the party succeeds; a moved Release 1 profile carries its member's name, phone and ward.

**R5-2 Party volunteer API** (backend)
- Files: `schemas/party.py`, `schemas/volunteers.py`, `services/volunteers.py`, `services/membership.py` (new request kind, join without a volunteer part), `services/dashboard.py`, `api/routers/party.py`, `api/routers/party_volunteers.py`, tests.
- Tests: a registration is one queued insert and applies as a new, untouched or revived volunteer; a centre outside the ward is refused; `other` without its text is refused; the officer list and CSV show party volunteers only; the dashboard counts by the volunteer's own ward.

**R5-3 Campaign volunteer API** (backend)
- Files: `api/routers/join.py`, new `api/routers/volunteers.py` or `campaigns.py`, `services/volunteers.py`, `tests/test_route_guards.py`, tests.
- Tests: a place outside the campaign's area is refused; a closed link, a non-approved aspirant and a locked campaign refuse a registration; a manager sees only their campaign's volunteers and another campaign's id answers 404; a mobilizer and the aspirant get 403; withdrawal deletes the row and answers the same for any code.

**R5-4 Party volunteer page** (frontend)
- Files: `pages/public/Volunteer.jsx`, `JoinParty.jsx`, `PublicLayout.jsx`, `Gate.jsx`, `pages/party/Volunteers.jsx`, `api/hooks`, contract, tests.
- Tests: the form sends the fields the route takes; Other opens its text box and is required; the officer list shows profession and polling station.
- Depends: R5-2.

**R5-5 Campaign volunteer pages** (frontend)
- Files: `pages/public/CampaignVolunteer.jsx`, the withdraw page, `pages/campaign/Volunteers.jsx`, `helpers.js` (manager menu), `CampaignLinkModal.jsx`, `Gate.jsx`, `api/hooks`, contract, tests.
- Tests: the place pickers offer only the campaign's area; a closed link shows closed; the manager's page lists and moves a volunteer.
- Depends: R5-3.

**R5-6 Integration** (lead)
- Both test lanes; `docs/SYSTEM.md`; one release critic against section 4 only.

---

## 4. Rubric for the release critic (frozen before building)

The critic judges these points and nothing wider. A finding outside them is
listed as non-blocking.

1. `/volunteer` and a campaign's `/volunteer/<code>` ask for first and last name, email, phone, constituency, ward, polling station, profession (Other with text), one or more of the ten areas (Other with text), preferred contact and consent, and refuse a submission missing any of them.
2. A campaign's page offers and accepts only places inside its seat's area, and is open only when its sign-up link is open, its aspirant approved or absent, and its access active or grace.
3. The party form's answer and its single insert are the same for a new, known or withdrawn phone; a campaign's answer is the same for a new or known phone.
4. A campaign's volunteers are seen and changed only by its manager; the party register, its CSV and the dashboard hold party volunteers only.
5. Each withdrawal link works once; a party volunteer is kept as withdrawn, a campaign volunteer is deleted.
6. The consent wording shown is the wording stored with the volunteer.
7. Both test lanes pass; existing tests pass unchanged except where this design changes volunteer fields or the join form's volunteer part.

---

## 5. Risks

| # | Risk | Effect if missed | Mitigation |
|---|---|---|---|
| 1 | A campaign volunteer reaches the party register or dashboard | Campaign data leaves the campaign | Every party read filters `campaign_id IS NULL`; rubric 4 |
| 2 | The party form shows who is registered | A phone's membership of the register leaks | The same queue as the join form; rubric 3 |
| 3 | Dropping the member link loses Release 1 volunteers | Dev data lost | The migration copies the member's details first; tested |
| 4 | 27,273 centres in one picker | A slow page | Centres load per ward only |
| 5 | Required email turns away people without one | Fewer volunteers | Taken from the sample on purpose; one schema change to relax it |
