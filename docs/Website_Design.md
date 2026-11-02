# Release 4: Public Website and Party Dashboard

Technical design for Release 4 of `docs/Implementation_Plan.md`. It builds on
`docs/Identity_Access_Design.md`, `docs/Aspirants_Design.md` and
`docs/Subscriptions_Design.md` and keeps their principles: campaign access
comes only from `campaign_members`, party access only from `party_roles`, and
nothing in `api/scope.py` reads a party table.

Status: approved 2 November 2026.

Decisions taken by Jeremy on 2 November 2026:

1. **The public site is at `/`; sign-in moves to `/signin`.** The superuser's
   console moves from `/` to `/console`. `/campaign/...` and `/party/...` stay.
2. **Leadership, news and events are two small tables**, `party_leaders` and
   `party_posts`, edited by the superuser. Photos are HTTPS URLs; there is no
   upload.
3. **The public Events page lists the party's own events only.** Campaign
   events stay inside each campaign.
4. **The dashboard shows upcoming campaign events as counts** by county and
   seat, never titles or venues.

Settled by the plan, not a decision: the dashboard and the website editor are
for the Party Super Admin (the superuser) only ("Version 1 Roles": reports
belong to the super admin). A full CMS, maps and file upload stay deferred.

---

## 1. What exists today

| Piece | Where | What R4 relies on |
|---|---|---|
| Party settings | `models/party.py` `PartySettings`; `GET /api/party/`, `PUT /api/admin/party/` | Name, short name, logo URL, colours, contacts, address, description, manifesto text and URL, social links |
| Settings editor | `frontend/src/components/Admin.jsx` (party section) | The superuser already edits the fields above |
| Public pages | `pages/public/JoinParty.jsx`, `WithdrawParty.jsx`, `WithdrawVolunteer.jsx`; `pages/public/colours.js` | Party branding on a public page |
| Routes | `frontend/src/Gate.jsx` `AppRoutes`, `Root`, `Inside` | Public paths listed before `/*`; `/` renders `Login`, then the console for a superuser |
| Party portal | `pages/party/Portal.jsx` `PAGES` | One menu entry per office; the superuser sees all |
| Registers | `party_members` (status, ward), `volunteer_profiles` (status, interests), `aspirants` (status, seat, area, campaign) | Dashboard counts |
| Campaigns | `campaigns` (seat, county, constituency, ward), `events` (ward, scheduled date, status) | Dashboard counts |
| Subscriptions | `services/billing.py` `access`, `revenue` | Active subscriptions and revenue |
| Route inventory | `backend/tests/test_route_guards.py` `PUBLIC_ROUTES` | New public routes are added there on purpose |
| Contract | `contracts/frontend-api.json`, `frontend/tests/contract.test.js` | Every route the frontend calls |

---

## 2. Design

### Principles

1. **Public pages read only published content.** A draft leader or post never
   leaves the server on a public route.
2. **The dashboard reads counts, never campaign records.** Campaign events are
   counted by county and seat; no title, venue, supporter or phone leaves a
   campaign.
3. **Text is shown as text.** Content is rendered with React's escaping; no
   field is rendered as HTML. Image fields accept `https://` URLs only.

### Data model

One revision, `public_content`, on top of `subscriptions`.

#### `party_leaders`

| Column | Rule |
|---|---|
| `id` | UUID PK |
| `name` | `varchar(150)`, required |
| `position` | `varchar(150)`, required (e.g. "Party Leader", "Secretary General") |
| `bio` | text, default `''` |
| `photo_url` | `varchar(500)`, default `''`; empty or `https://...` |
| `sort_order` | integer, default 0; lower first |
| `published` | boolean, default false |
| `created_at`, `updated_at` | |

#### `party_posts`

| Column | Rule |
|---|---|
| `id` | UUID PK |
| `kind` | `news, event` |
| `title` | `varchar(150)`, required |
| `body` | text, default `''` |
| `image_url` | `varchar(500)`, default `''`; empty or `https://...` |
| `event_date` | date NULL; `CHECK ((kind = 'event') = (event_date IS NOT NULL))` |
| `venue` | `varchar(150)`, default `''`; events only |
| `published_on` | date NULL; set to today (Nairobi) the first time it is published, kept after |
| `published` | boolean, default false |
| `created_at`, `updated_at` | |

Index on `(kind, published, event_date)` and `(kind, published, published_on)`.

### Public routes (no login)

| Route | Returns |
|---|---|
| `GET /api/party/leaders/` | Published leaders by `sort_order`, then name |
| `GET /api/party/posts/?kind=news` | Published news, newest `published_on` first, paged (20) |
| `GET /api/party/posts/?kind=event` | Published events with `event_date >= today`, soonest first |
| `GET /api/party/posts/{id}/` | One published post; 404 for a draft or unknown id |

All four join `PUBLIC_ROUTES` in `test_route_guards.py`.

### Editing routes (superuser)

`/api/admin/party/leaders/` and `/api/admin/party/posts/`: list (drafts
included), create, update (`PATCH`), delete. Audited as `party.leader.create`,
`.update`, `.delete` and `party.post.*`; detail holds ids, kind and the
published flag, never text.

### Dashboard (superuser)

`GET /api/party/dashboard/` with optional filters `county`, `constituency`,
`ward`, `seat`, `aspirant`, `from`, `to` (default: the current calendar year
for revenue, the next 30 days for events).

| Figure | Counts |
|---|---|
| Approved members | `party_members.status = approved` |
| Pending applications | `party_members.status = pending` |
| Active volunteers | `volunteer_profiles.status = active` |
| Volunteers by place and interest | Active volunteers per county, and per interest |
| Approved aspirants | `aspirants.status = approved` |
| Active campaigns | Campaigns that answer their logins today: aspirant approved or none, and access state `active`, `grace_period` or `read_only` |
| Active CRM subscriptions | Subscriptions in `active` or `grace_period` today |
| Upcoming campaign events | Planned campaign events with `scheduled_date` in `[from, to]`, counted per county and per seat |
| Campaigns by county and seat | Campaign count per county × seat |
| Recorded CRM revenue | `billing.revenue` total and count for `[from, to]` |

Filters: a place filter keeps members and volunteers living in it, and
campaigns, aspirants and events whose area lies inside it (a county filter
keeps that county's ward, constituency and county campaigns; a ward filter
keeps only that ward's MCA campaigns and events in that ward). `seat` keeps
aspirants, campaigns, their events and their revenue for that seat. `aspirant`
keeps that aspirant's campaign, its events and its revenue. Revenue from a
deleted campaign counts only when no place, seat or aspirant filter is set.

### Frontend

| Where | Change |
|---|---|
| `Gate.jsx` | Public routes `/`, `/about`, `/leadership`, `/manifesto`, `/news`, `/news/:id`, `/events`, `/join-party`, `/signin`; signed-in apps at `/console/*`, `/campaign/*`, `/party/*`. `/signin` shows `Login`, or sends a signed-in user to their home (superuser `/console`, staff `/party`, campaign login `/campaign`). A signed-out visit to a signed-in path goes to `/signin` |
| `components/Admin.jsx`, `Portal.jsx` | Console links point at `/console` instead of `/` |
| `components/PublicLayout.jsx` (new) | Header with logo, party name and menu (Home, About, Leadership, Manifesto, News, Events, Join, Sign in), footer with contacts and social links; party colours from settings |
| `pages/public/` (new pages) | `Home` (description, three latest news, three next events, join button), `About` (description, contacts, address), `Leadership`, `Manifesto` (text and a link to the manifesto URL), `News`, `Post`, `Events`. `JoinParty` moves inside the layout |
| `pages/party/Website.jsx` (new) | Superuser: leaders and posts tables with add, edit, publish, delete |
| `pages/party/Dashboard.jsx` (new) | Superuser: filters, the figures as tiles, the two count tables (campaigns by county × seat, upcoming events by county and seat), volunteers by county and interest |
| `Portal.jsx` `PAGES` | `Dashboard` and `Website`, superuser only; the superuser lands on Dashboard |

---

## 3. Tickets

The migration runs first and alone (R4-1). A route enters
`contracts/frontend-api.json` in the frontend ticket that first calls it.

**R4-1 Leaders and posts tables** (schema) — done 2 Nov 2026
- Files: new `models/content.py`, `models/enums.py` (`PostKind`), `models/__init__.py`, new revision `public_content`, `tests/test_models.py`.
- Tests: an event without a date fails at the database; a news post with a date fails.

**R4-2 Public content API** (backend) — done 2 Nov 2026
- Files: new `schemas/content.py`, new `services/content.py`, `api/routers/party.py` (public reads), `api/routers/admin.py` (editing), `tests/test_route_guards.py` (`PUBLIC_ROUTES`), new `tests/test_public_content_api.py`.
- Tests: a draft leader or post is absent from the public routes and 404 by id; publishing sets `published_on` once; past events are not listed; a non-`https` image URL is refused; a non-superuser gets 403 on every editing route.

**R4-3 Dashboard API** (backend) — done 2 Nov 2026
- Files: new `services/dashboard.py`, `schemas/dashboard.py`, `api/routers/party.py`, new `tests/test_dashboard_api.py`.
- Tests: each figure counts what the table says on a small fixed world; a county filter drops another county's members and campaigns; a seat filter narrows revenue; only the superuser gets 200.

**R4-4 Routes and sign-in** (frontend) — done 2 Nov 2026
- Files: `Gate.jsx`, `components/Login.jsx`, `components/Admin.jsx`, `pages/party/Portal.jsx`, tests.
- Tests: `/` shows the public home signed out and signed in; `/signin` sends each kind of login to its home; a signed-out visit to `/console` lands on `/signin`.
- Depends: none (the home page can be a placeholder until R4-5).

**R4-5 Public pages** (frontend) — done 3 Nov 2026
- Files: new `components/PublicLayout.jsx`, new pages in `pages/public/`, `api/hooks`, `contracts/frontend-api.json` (public content routes), tests.
- Tests: the home page shows published news and events from the API; the leadership page lists leaders in order; the menu links reach every page.
- Depends: R4-2, R4-4.

**R4-6 Website editor** (frontend)
- Files: new `pages/party/Website.jsx`, `Portal.jsx`, `api/hooks`, `contracts/frontend-api.json` (editing routes), tests.
- Tests: adding, publishing and deleting a post call the right routes; an event needs a date before it saves.
- Depends: R4-2.

**R4-7 Dashboard page** (frontend)
- Files: new `pages/party/Dashboard.jsx`, `Portal.jsx`, `api/hooks`, `contracts/frontend-api.json` (`/api/party/dashboard/`), tests.
- Tests: the tiles show the API's figures; changing a filter refetches with it.
- Depends: R4-3.

**R4-8 Integration** (lead)
- Both test lanes; `docs/SYSTEM.md` (public site, dashboard, routes, counts); one release critic against section 4 only.

---

## 4. Rubric for the release critic (frozen before building)

The critic judges these points and nothing wider. A finding outside them is
listed as non-blocking.

1. Signed out, `/`, `/about`, `/leadership`, `/manifesto`, `/news`, `/events` and `/join-party` render with the party's name, logo and colours, and link to each other and to `/signin`.
2. No public route returns a draft leader or post, and the public routes need no login.
3. Only the superuser can create, edit, publish or delete leaders and posts; each change is audited without its text.
4. Every sign-in lands on its home: superuser `/console`, party staff `/party`, campaign login `/campaign`; every existing console, portal and campaign screen still works at its address.
5. Each dashboard figure matches the definition in "Dashboard" for a fixed set of records, with and without each filter.
6. No dashboard answer carries a campaign event's title or venue, or any supporter, member or phone detail; only the superuser gets the dashboard.
7. Both test lanes pass; existing tests pass unchanged except where this design changes a route's address.

---

## 5. Risks

| # | Risk | Effect if missed | Mitigation |
|---|---|---|---|
| 1 | Moving the console off `/` | A bookmark or link sends the superuser to the public home | The site's header shows "Portal" to a signed-in user; tests cover each home |
| 2 | A draft leaks through a public route | Unpublished text is public | One query helper adds `published = true` for every public read; rubric 2 |
| 3 | An image URL points at an unsafe scheme | Script or tracking on the public site | Only `https://` accepted; text rendered as text |
| 4 | Dashboard filters miscount areas | Wrong totals shown to party leaders | The filter rule is written above and tested per figure |
| 5 | Dashboard queries slow with many campaigns | A slow page | Counts are SQL aggregates; subscription state is computed in Python over campaigns, as in R3, fine for hundreds |
