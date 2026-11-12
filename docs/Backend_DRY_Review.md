# Backend DRY / KISS Review

Scope: `backend/src/backend` (26,209 lines, working tree of 2026-11-10). Tests, evals, the migration and the CSV data are out of scope. Comments and docstrings were ignored: every finding below rests on the code itself.

Status: done. Every family (B1 to B41) is in the code, in the commits titled "Backend review ..."; B32's second half, the seed loading through the imports, is a88f8c9. The rest of this file is the review as written; line references are to the tree before those commits.

## 1. Method

1. `pylint --disable=all --enable=duplicate-code --min-similarity-lines=5` with comments, docstrings, imports and signatures ignored (24 hits).
2. An AST script that strips docstrings and compares every function body, first exactly, then with variable names blanked (13 identical groups, 14 more after renaming).
3. A second AST script that hashes runs of two sibling statements with names and strings blanked, over everything except `seed/`, `models/` and `schemas/` (64 repeated runs).
4. Greps for known idioms (`token_urlsafe`, `HTTP_429`, `tzinfo`, `full_name or username`, phone refusals).
5. Each hit was then read in the source. Files read in full: `api/deps.py`, `api/scope.py`, `api/errors.py`, routers `admin`, `workspace_site`, `party`, `messages`, `party_messages`, `party_members`, `party_volunteers`, `party_aspirants`; services `home`, `content`, `messages`, `party_messages`, `texting`, `membership`, `volunteers`, `aspirants`, `campaign_volunteers`, `payments_in`, `payouts`, `audit`, `errors`, `party`, `site`. Every other file was read only at the lines the tools flagged.

6. Second pass: a script listing every user-facing string of 28+ characters that appears in more than one place (40 strings), then full reads of `services/admin.py`, `accounts.py`, `team.py`, `team_signup.py`, `privacy.py`, `nominations.py`, `payout_flow.py`, `candidates.py`, `campaign_page.py` and routers `events`, `supporters`, `targets`, `mobilizers`, `agents`, `assignments`.

7. Third pass: every remaining file read end to end with its real line numbers: all of `services/`, `api/`, `schemas/`, `models/`, `seed/`, plus `cli.py`, `config.py`, `main.py`, `security.py` and `db/`. Nothing in `backend/src/backend` is now unread. Out of scope and unread: `tests/`, `evals/`, the Alembic migration, the CSV data.

Line counts in the "saves" column are estimates from the spans listed, not measured diffs.

## 2. Findings at a glance

| # | Family | Sites | Saves (est.) | Risk | Priority |
|---|--------|-------|--------------|------|----------|
| B1 | Home-item and post CRUD routes written out by hand in `admin.py` | 28 + 4 routes | 150 lines | Low | 1 |
| B2 | Register search, place filters and paging (members vs volunteers) | 2 services, 3 `_like` | 70 lines | Low | 1 |
| B3 | Inbox run twice per officer request, called by hand 15 times | 15 calls | 15 lines, 1 query pass | Low | 1 |
| B4 | Rate-limit check and `_client` imported from another router | 18 checks, 7 imports | 40 lines | Low | 1 |
| B5 | SMS drafts: campaign vs party message services | 2 services | 60 lines | Medium | 2 |
| B6 | Guarded status move ("changed meanwhile") | 11 sites | 60 lines | Medium | 2 |
| B7 | Paystack HTTP client and body parser | 2 services | 25 lines | Low | 2 |
| B8 | Upload handlers and private file responses | 3 + 2 routers | 35 lines | Low | 2 |
| B9 | Schema validators (`_plain`, consent, `_line`/`_short`, address checks) | 25+ | 80 lines | Low | 2 |
| B10 | Integrity-error ladder in `api/errors.py` | 10 branches | 30 lines | Low | 2 |
| B11 | Leader CRUD repeats the generic `home` CRUD | 1 service | 50 lines | Low | 3 |
| B12 | CSV export: `_cell`, writer, response | 3 routers | 25 lines | Low | 3 |
| B13 | Small helpers copied: hash, UTC, codes, phone, names, places, area filter | 35+ sites | 60 lines | Low | 3 |
| B14 | Settings "replace and list changed fields" | 3 services | 20 lines | Low | 3 |
| B15 | New-login response builders | 5 sites | 20 lines | Low | 3 |
| B16 | Place guard chain in create routes | 4 routers | 15 lines | Low | 3 |
| B17 | `updated_at` column block | 4 model files | 25 lines | Low | 3 |
| B18 | Test-send code in `ops` and `setup` | 2 services | 15 lines | Low | 3 |
| B19 | Campaign text audience rebuilt inside the events router | 1 router vs `messages.py` | 25 lines | Medium | 2 |
| B20 | Candidate page written twice (party install vs aspirant install) | 2 services | 40 lines | Low | 2 |
| B21 | "This place belongs to this campaign" checks | 7 files | 50 lines | Medium | 2 |
| B22 | Row by id or NotFound | 21 sites | 40 lines | Low | 3 |
| B23 | Logins on a campaign, and a login's place on it | 10 sites | 25 lines | Low | 3 |
| B24 | Sign a login out | 8 sites | 8 lines | Low | 3 |
| B25 | Site identity fields and the colour contrast check | 2 schemas | 20 lines | Low | 3 |
| B26 | Nomination fee rules and fee stamp | 2 services | 12 lines | Low | 3 |
| B27 | "Own rows" for a mobilizer or agent | 2 routers, 6 sentinels | 15 lines | Low | 3 |
| B28 | Erased check written inline beside `refuse_erased` | 3 sites | 6 lines | Low | 3 |
| B29 | Refusal wording written twice (pre-check and race handler) | 6 pairs | 10 lines | Low | 3 |
| B30 | One-time tokens, three implementations | 3 files | 30 lines | Medium | 2 |
| B31 | Geography listings | 5 places | 40 lines | Low | 2 |
| B32 | Two geography importers, and four copies of the upsert loop | 2 files | 70 lines | Medium | 3 |
| B33 | Campaign loader tuple and candidate name | 3 + 3 sites | 10 lines | Low | 3 |
| B34 | Published party posts queried in three places | 3 services | 15 lines | Low | 3 |
| B35 | Party member helpers: place trio, approved check | 9 + 4 sites | 20 lines | Low | 3 |
| B36 | Schemas: `{id, name}` model 8 times, page wrapper 3 times, twin classes | 15 classes | 40 lines | Low | 2 |
| B37 | Schemas: Create/Update pairs declare every field twice | 8 pairs | 90 lines | Medium | 3 |
| B38 | Schemas: field specs retyped | 30+ fields | 30 lines | Low | 3 |
| B39 | Models: partial unique index with its WHERE typed twice | 20 indexes | 60 lines | Low | 2 |
| B40 | Models: the same column written out per table | 60+ columns | 110 lines | Low | 2 |
| B41 | CLI re-implements `admin.set_email` | 1 command | 8 lines | Low | 1 |
| K1-K16 | KISS items (section 4) | - | - | Low | 3 |

## 3. Findings

### B1 - Home-item and post CRUD routes in `admin.py`

`api/routers/workspace_site.py:125-177` has `_items(path, model, create, update, read)`, which registers list, add, change and remove for one home-page model in one call. `api/routers/admin.py:343-502` writes the same four handlers out by hand for seven models (slides, issues, documents, values, organs, results, videos): 28 handlers, 160 lines, every body a one-line call to `home.every/create/update/delete`. The AST script reports all 28 as identical to the factory's four inner functions once names are blanked.

The post routes repeat too: `admin.py:116-140` and `workspace_site.py:101-122` are the same four handlers with a different guard.

Fix: move `_items` to a shared module (for example `api/content_routes.py`) taking the router and the guard type as arguments. `admin.py` then holds seven lines for the seven models, `workspace_site.py` four. Add a `_posts(router, guard)` beside it.

Watch: the routes on `party_router` (values, organs, results) must stay on `party_router`. Route names change (`party_slides` becomes the factory's name), which only shows in OpenAPI operation ids. `evals/test_frontend_contract.py` and `tests/test_route_guards.py` cover the paths and guards.

### B2 - Register search, place filters and paging

`services/membership.py:398-472` and `services/volunteers.py:267-354` are the same register code over two models:

- `_like` is byte-identical (`membership.py:419`, `volunteers.py:267`), and `aspirants.py:275` inlines it a third time.
- The name-or-phone search with the `07...` to `+254...` rule: `membership.py:435-444` and `volunteers.py:311-319`.
- The county, constituency, ward filters: `membership.py:447-452` and `volunteers.py:329-334`.
- `given()`: `membership.py:406-416` and `volunteers.py:281-293`.
- Count-then-page: `membership.py:456-467` and `volunteers.py:338-349`; `export_rows` at `:470` and `:352`.

Fix: one `services/register.py` with `person_matches(q)` (returns the WHERE clause on `PartyMember`), `in_place(statement, filters)`, `page(session, statement, id_column, limit, offset)`, and a `PlaceFilters` base dataclass that owns `q`, `county`, `constituency`, `ward` and `given()`. `MemberFilters` and `VolunteerFilters` subclass it and add their own fields.

KISS inside the fix: SQLAlchemy already escapes LIKE input. `services/audit.py:86-88` uses `icontains(..., autoescape=True)` and `startswith(..., autoescape=True)`. Using the same here deletes `_like` and all the `escape="\\"` arguments.

Tests that cover it: `tests/test_party_members_api.py`, `tests/test_party_volunteers_api.py`, `tests/test_party_aspirants_api.py`.

### B3 - The party inbox is run twice per officer request

`api/deps.py:144` runs `membership.process_requests(session)` inside `require_party_role` for every officer who is not a superuser. The routers then call it again as the first line of each handler: 6 times in `party_aspirants.py`, 5 in `party_members.py`, 4 in `party_volunteers.py`. For an officer that is two passes over the inbox per request; for a superuser one.

Fix: move the call in `deps.py` above the `is_superuser` shortcut at `deps.py:138` and delete the 15 handler calls. One call, in one place, for every caller.

Watch: superuser requests through the other `require_party_role` guards (party messages, branch officials) would then also drain the inbox. That is one extra indexed read on an empty queue.

`party_members.py:133-134`, `:146-147` and `:157-158` also repeat the same two closing lines (re-read the member, build `MemberDetail` with `with_logins`). One `_detail(session, member_id)` covers all three.

### B4 - Rate-limit boilerplate and a private function shared across routers

`_client` lives in `api/routers/join.py:110` and is imported, underscore and all, by seven other routers (`aspirant_site`, `auth`, `candidates`, `party`, `pay`, `sms_callbacks`, `team_signup`). The check around it is written 18 times:

```python
if not X.allow(_client(request)):
    raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries; try later.")
```

`auth.py:61-63` already wraps this as `_too_many(request, limit)` but only `auth.py` uses it.

Fix: put `client_key(request)` in `services/ratelimit.py` (or `api/deps.py`) and give `RateLimit` a `check(request, message="Too many tries; try later.")` that raises. Each site becomes one line. `party.py:77-81` declares five limits with the same numbers; keep them separate (each is its own bucket) but the declarations can share a `HOURLY = dict(limit=20, window=3600)`.

The same cross-router private imports exist for `_cell` (`agents.py:12` from `party_members`), `_read` (`party_nominations.py:13` from `party_aspirants`) and `read` (`party_nominations.py:14`, `workspace_site.py:15`). Shared helpers belong in a module that is not a router.

### B5 - SMS drafts: `services/messages.py` vs `services/party_messages.py`

The audiences differ and should stay separate. The draft life cycle does not:

- `text_of` is identical: `messages.py:20`, `party_messages.py:36`.
- `_decide`: `messages.py:136-149` and `party_messages.py:171-186`, the same guarded UPDATE with the model swapped (the party one adds the "not your own draft" rule).
- `get`: `messages.py:208`, `party_messages.py:164`.
- `send` tail (set `recipients`, audit with provider, accepted, failed): `messages.py:167-182`, `party_messages.py:203-217`.
- `listing`: the delivery counts by status (`messages.py:225-231`, `party_messages.py:240-246`) and the drafter/decider names (`messages.py:232-236`, `party_messages.py:247-251`).

Fix: add to `services/texting.py` (it already owns `FOOTER`): `text_of(body)`, `decide(session, model, message, status, actor, note)`, `delivery_counts(session, column, ids)` and `names_of(session, user_ids)`. The party service keeps its own-draft check before calling `decide`.

Related KISS item: both routers build a single message's response by running the whole listing and picking one row (`routers/messages.py:46-48`, `routers/party_messages.py:27-28`). Every draft, send and decline therefore loads every message plus three or four lookups. Let `listing` take an optional `ids` filter.

Tests: `tests/test_messages_api.py`, `tests/test_party_messages_api.py`.

### B6 - Guarded status move

The same statement appears eight times: UPDATE where `id` matches and `status` is still the old one, then refuse when `rowcount != 1`.

- `membership.py:60-73` `_set_status` and `campaign_volunteers.py:45-58` `write_status`: identical apart from the model and one word in the message.
- `aspirants.py:133-140`, `nominations.py:176-182`, `:328-335`, `:353-362`.
- `messages.py:140-149`, `party_messages.py:177-186` (B5).

`check_move` is also written twice with the same shape (`membership.py:54`, `campaign_volunteers.py:39`).

Fix: one helper, for example in `db/session.py`: `move_row(session, row, old_status, refusal, **values)` that runs the UPDATE on `type(row)`, raises `Refused(refusal)` on a miss and applies `set_committed_value`. A `check_move(table, frm, to, noun)` beside the move tables.

Risk is medium because this is the concurrency guard. Do it as its own change with `tests/test_membership_service.py`, `tests/test_party_members_api.py`, `tests/test_nominations_api.py` and `tests/test_party_volunteers_api.py` run before and after.

### B7 - Paystack client

`services/payments_in.py:71-94` and `services/payouts.py:104-109, 126-128, 173-179` hold the same `_body`, the same `__init__(secret_key, transport)` and the same `_client()`. `payments_in.py:31` already imports `PAYSTACK_API` from `payouts`.

Fix: `services/paystack.py` with `PAYSTACK_API`, `client(secret_key, transport)`, `body(response)` and `paystack_signed` (today in `payouts.py:245`, though it signs charge webhooks too). The two `DEAD` sets differ on purpose (charges vs transfers) and stay where they are.

### B8 - Upload handlers

Three routers read an upload, call `files.store`, and translate two exceptions: `files.py:47-63`, `workspace_site.py:58-74`, `branch_officials.py:84-98`.

Two simplifications:

1. `except Refused as error: raise HTTPException(400, ...)` is dead weight in all three. `api/errors.py:52-59` already answers every `Refused` with 400.
2. `files.TooLarge` subclasses `Refused` (`services/files.py:42`). Map it to 413 once in `errors.py` and the three `try` blocks go away entirely.

What is left is one call; a small `store_upload(session, file, area=..., public=..., actor=...)` next to `files.store` removes the repeated `file.read(files.PDF_MAX + 1)`, `name=file.filename or ""`, `declared_type=file.content_type`.

Serving a private stored file is also written twice: `branch_officials.py:108-116` and `party_nominations.py:132-135`.

### B9 - Schema validators

- `_plain` validators that only call `plain_text` on some fields: 12 classes (`common.py:81`, `party.py:69`, `:118`, `:195`, `:207`, `aspirants.py:79`, `candidates.py:107`, `:137`, `team_signup.py:49`, `volunteers.py:52`, plus the two model validators in `party.py:47` and `site.py:101`). `common.py:42` already shows the short form (`CampaignTitle` with `AfterValidator(plain_text)`). Add `Plain = Annotated[str, AfterValidator(plain_text)]` and `PlainLines` and annotate the fields.
- `_consent_is_required`: three identical copies (`campaign.py:225`, `join.py:43`, `party.py:130`) and two with other wording (`party.py:81`, `:212`). One `consent(message)` factory returning an annotated type.
- `_line(limit)` in `candidates.py:17` and `_short(limit)` in `content.py:293` are the same function; `Place` at `content.py:59` is the same lambda again.
- `_image`, `_pdf`, `_https` (`content.py:18-42`) are one function with a different message and an "uploaded file allowed" switch.
- `MemberMove` (`party.py:190`) and `AspirantMove` (`aspirants.py:73`) carry the same `reason` field and validator. `VolunteerUpdate` (`volunteers.py:46`) and `CampaignVolunteerUpdate` (`candidates.py:129`) are the same class.
- Two email rules: `content.py:276` checks only for "@" and spaces, `site.py:32` uses the `EMAIL` pattern. The branch form should use `site.Email`.

Covered by `tests/test_schemas.py`. Error wording must not change, since the frontend shows it.

### B10 - Integrity-error ladder

`api/errors.py:71-109` repeats `if any(name in str(exc.orig) for name in X): return _detail(msg, 400)` ten times. Replace the ten constants and ten branches with one ordered list of `(names, message)` pairs and a loop. Order matters (`ONE_MANAGER` before `ONE_PLACE`), and a list keeps it.

### B11 - Leader CRUD

`services/content.py:84-134` (`leaders`, `create_leader`, `_leader`, `update_leader`, `delete_leader`, `_audit`) is the generic CRUD in `services/home.py:56-117` written for one model. `published_leaders` (`content.py:21`) is `home.published`.

Fix: add `PartyLeader` to `home.NAMES` and to `_ordered` (it sorts by `sort_order, name`), and point the four admin routes at `home`. The audit action stays `party.leader.*`; the subject type would change from `party_leader` to `leader` unless `NAMES` carries it, so let `NAMES` map to `(action_name, subject_type)`.

With B1 the leader routes then also come from the factory.

### B12 - CSV export

`_cell` and `FORMULA_LEADS` are identical in `party_members.py:51-56` and `party_volunteers.py:38, 66-68`; `agents.py:12` imports the first. The writer and response are repeated at `party_members.py:106-127`, `party_volunteers.py:125-152` and in `agents.py`.

Fix: `api/csv.py` with `cell(text)` and `csv_response(filename, columns, rows)`.

The `plain_text(q)` try/except that turns a `ValueError` into a 400 is written four times (`party_aspirants.py:72-75`, `party_console.py:32`, `party_members.py:41-44`, `party_volunteers.py:49-52`). An annotated query type (`Annotated[str | None, AfterValidator(plain_text)]`) does the same through the existing validation handler; the message gains a `q: ` prefix.

### B13 - Small helpers copied

| Helper | Copies | Fix |
|--------|--------|-----|
| SHA-256 hex of a token | `login_links.py:36`, `setup.py:41`, `auth.py:66` | `security.sha256_hex` |
| "Naive datetime means UTC" | `login_links.py:40`, `setup.py:45`, inline at `payments_in.py:294`, `auth.py:283`, `reconcile.py:55`, `models/payment.py:65` | `clock.as_utc` |
| Withdraw code `token_urlsafe(18)` | `membership.py:51` (named), then inline at `join.py:186`, `campaign_volunteers.py:182`, `privacy.py:242`, `subscribers.py:21`, `volunteers.py:404` | move `new_withdraw_code` to `security.py`, use it everywhere |
| Short code `token_urlsafe(9)` | `models/campaign.py:99`, `:104`, `models/event.py:53`, `party_workspace.py:133`, `team_signup.py:328` | `security.new_short_code` |
| Phone refusal after `normalise_phone` | `join.py:180`, `party.py:221`, `party.py:292`, `campaign_volunteers.py:170`, `ops.py:405`, `ops.py:431` | `sms.require_phone(raw)` raising `Refused` |
| `full_name or username` | 9 sites, for example `agents.py:31`, `campaigns.py:45`, `join.py:136`, `payments.py:118`, `messages.py:234`, `party_messages.py:249` | `User.display_name` property |
| Aspirant's area name | `party_nominations.py:158`, `candidates.py:48`, `console.py:30` (identical) | `Aspirant.area_name` property |
| County of a seat | `campaign_page.py:53`, `candidates.py:53` (same shape on `Campaign` and `Aspirant`) | one `county_name(row)` |
| Narrow a query to an `Area` | `agents.py:33`, `assignments.py:36`, `team_signup.py:183`, and `scope.py:104-108` | `Area.narrow(statement, model)` in `permissions.py` |
| `full_name` property | `models/team.py:79`, `models/user.py:110` | leave, or a two-line mixin |
| Load a login with its party roles | `admin.py:528`, `:568`, `:595` | `_login_with_roles(session, user_id)` |

### B14 - Settings replace

`services/party.py:21-39` and `services/site.py:37-55` are the same function with a different audit name. `services/branches.py:104-108` uses the same "list changed fields, then set them all" lines.

Fix: `replace_fields(row, values) -> list[str]` (one place for the idiom), and one `update_settings(session, row, payload, action, *, actor)` used by both settings services.

### B15 - New-login responses

Five handlers copy fields off a `User` into a response by hand: `team.py:48-54` and `party_workspace.py:83-89` (`ManagerCreated`), `team.py:66-72` (`StaffCreated`), `admin.py:248-254` and `party_aspirants.py:157-163` (`AdminUserCreated`). `NewLogin` is an `ORMModel` with `from_attributes`, so `Model.model_validate(created).model_copy(update={"invite": invite, ...})` or one `new_login(model, user, invite, **extra)` helper replaces all five.

### B16 - Place guards in create routes

`events.py:91-93`, `targets.py:64-66`, `mobilizers.py:47-51` and `users.py:32-39` each call `require_visible_campaign`, `require_in_area` and `require_ward_in_campaign` on the same four values. One `scope.require_place(session, user, action, campaign_id, ward, centre) -> Campaign` covers the three calls.

`scope.require_centre_in_ward_race` (`scope.py:210-221`) is `async` and takes `session` and `ward_id` but uses neither. Make it a plain function of `(campaign, centre_id)`.

### B17 - `updated_at` column

The eight-line `updated_at` column with `onupdate` is copied in `models/content.py`, `models/nominations.py`, `models/party.py` and `models/volunteer.py`. `db/base.py` already has `TimestampMixin` for `created_at`; add `UpdatedAtMixin` beside it. The column definition is unchanged, so Alembic sees no difference (`tests/test_migrations.py` confirms).

### B18 - Test sends

`services/ops.py:404-423` (`test_sms`) and the `sms` branch of `services/setup.py:242-259` both normalise a phone, call `texting.send` with `TEST_TEXT`, audit, commit and word the outcome. One `texting.send_test(session, number, actor)` returning the result; each caller keeps its audit action and wording.

### B19 - Campaign text audience rebuilt in the events router (second pass)

`api/routers/events.py:147-207` (`invite_to_event`) builds a supporter audience by hand: consenting supporters of the campaign, narrowed by ward and by the caller's area (`events.py:156-166`), then `normalise_all` (`:168`), `texting.opted_out` (`:172`) and `payload.message.strip() + texting.FOOTER` (`:169`). `services/messages.py:45-72` (`_audience`, `recipients`) and `text_of` (`messages.py:20`) do the same for a campaign message. This is the third copy of `text_of` (B5 counted two).

The two differ in one filter: `messages._audience` drops supporters with an empty phone (`messages.py:50`); the events router keeps them and lets `normalise_all` report them as unusable. Decide which is right before merging.

Fix: move the invite into a service function that calls `messages.recipients` with an optional support-level filter, so one function decides who a campaign may text. The router keeps the dry-run switch and the response shape.

### B20 - Candidate page written twice (second pass)

`services/candidates.py` (party install) and `services/campaign_page.py` (aspirant install) both read and write a `CandidateProfile`:

- Create-or-replace the profile: `candidates.py:233-242` and `campaign_page.py:99-106`.
- `ProfileRead` from a profile or an empty one: `candidates.py:177-180` and `campaign_page.py:89-93`.
- `CandidateDetail` with the same profile and consent fields: `candidates.py:151-165` and `campaign_page.py:69-86`.
- `_county`: `candidates.py:53-58` and `campaign_page.py:53-58` (B13 listed only this one).
- `PLACES` loader tuples of the same shape: `candidates.py:40-45` and `campaign_page.py:29-34`.

Fix: keep both services (they find the profile differently) and share three helpers in `candidates.py`: `save_profile(session, profile, values, **keys)`, `profile_read(profile)` and `profile_fields(profile)` for the `CandidateDetail` arguments.

### B21 - "This place belongs to this campaign" (second pass)

The rule "a ward must be inside the campaign's seat, and a centre must be in such a ward" is checked separately in seven files, each with its own wording:

- `api/scope.py:189-207` `require_ward_in_campaign`
- `services/team.py:180-188` (`set_areas`)
- `services/team_signup.py:70-73` (`centres_of`) and `:82-105` (`_place`)
- `services/agents.py:91-97` (`update`)
- `services/assignments.py:119-127` (`_place`)
- `services/campaign_volunteers.py:173-181` (`sign_up`)
- `services/admin.py:484-488` (`create_user`)

"That ward is not one this campaign works." is written three times (`scope.py:198`, `team.py:182`, `team_signup.py:73`), "That registration centre is not one this campaign works." twice (`agents.py:97`, `team.py:188`), "Pick a ward this campaign works." twice (`assignments.py:127`, `team_signup.py:92`).

Two smaller rules ride along:

- "This centre has a target": the same SELECT at `scope.py:230-234`, `accounts.py:187-191` and `team_signup.py:98-101`.
- "This mobilizer is on this campaign": `scope.py:242-250` and `assignments.py:88-92`, same wording.

Fix: put the rules in `services/targets.py` beside `ward_in_area`: `require_ward(session, campaign, ward_id)`, `require_centre(session, campaign, centre_id) -> RegistrationCentre` and `is_targeted(session, campaign_id, centre_id)`, all raising `Refused`. `scope.py` and the six services call them. Wording becomes one sentence per rule, so check the frontend does not match on the old sentences.

### B22 - Row by id or NotFound (second pass)

"Get the row; raise `NotFound('No such X.')` when it is missing" is written about 21 times, often as a private helper per model: `admin.py:62` `_campaign`, `admin.py:69` `_user`, `content.py:103` `_leader`, `content.py:165` `_post`, `home.py:72` `_get`, `messages.py:208` and `party_messages.py:164` `get`, `nominations.py:308-310` and `:402-404` (the same document check twice), `candidates.py:257` and `:272-274` (the same post lookup twice, while `content._post` exists), `privacy.py:318-324`, and in routers `payments_in.py:52-56`, `privacy.py:44-50`, `agents.py:127-129`, `assignments.py:84-86`.

Fix: one `get_or_refuse(session, model, row_id, noun, *, campaign_id=None)` in `db/session.py`. `home._get` is already this function for seven models.

Inconsistency found on the way: `admin.py:311-313` answers a missing user with `Refused` (400) while `_user` (`admin.py:69`), which answers `NotFound` (404), sits unused there. `routers/mobilizers.py` `_free_mobilizer` and `routers/payments.py:95-97` also answer 400. If "400 for an id in the body, 404 for an id in the path" is the rule, write it down; if not, use `NotFound`.

### B23 - Logins on a campaign (second pass)

- "Logins on this campaign" (User joined to CampaignMember): `admin.py:383-391` `logins_on`, `team.py:29-36` `team`, `team.py:39-44` `manager_of`, and the party workspace router's own manager query (`api/routers/party_workspace.py:48-52`).
- "This login's place on this campaign": `accounts.py:136-140`, `team.py:138-142`, `admin.py:333-337`.
- "Take a login off a campaign": `admin.py:342-346`, `team.py:62-66`, `api/routers/mobilizers.py:115-118`.

Fix: three functions in `services/accounts.py` (it already owns `add_member` and `campaign_of`): `logins_on(session, campaign_id, role=None)`, `member_of(session, campaign_id, user_id)` and `leave(session, campaign_id, user_id)`.

### B24 - Sign a login out (second pass)

`delete(AuthToken).where(AuthToken.user_id == ...)` appears eight times: `admin.py:232`, `:280`, `team.py:67`, `:121`, `team_signup.py:308`, `login_links.py:145`, `api/routers/account.py:137`, `api/routers/auth.py:124`. One `accounts.sign_out(session, user_id)`.

### B25 - Site identity fields and colour contrast (second pass)

`schemas/setup.py:22-41` (`SetupSite`) and `schemas/site.py:79-120` (`SiteSettingsUpdate`) declare the same nine fields with the same limits (`name`, `short_name`, `logo_url`, both colours, `contact_email`, `contact_phone`, `address`, `privacy_notice`) and the same two contrast checks with the same wording (`setup.py:36-39`, `site.py:117-120`).

Fix: a `SiteIdentity(WriteModel)` base holding the shared fields and a `_contrast` validator; both classes inherit it. Belongs with B9.

### B26 - Nomination fee rules (second pass)

Whether a fee can still be paid is decided twice: `nominations.py:378-383` (`mark_fee_paid`) and `payments_in.py:176-181` (`_fee_open`), the same three checks in the same order. The three fee fields are stamped twice: `nominations.py:384-386` and `payments_in.py:278-281`.

Fix: `nominations.require_fee_open(aspirant)` and `nominations.stamp_fee(aspirant, reference, marked_by_id, at)`; `payments_in` calls both.

### B27 - "Own rows" for a mobilizer or agent (second pass)

A caller with `Reach.OWN` sees only rows carrying their own mobilizer or agent id. `api/routers/assignments.py:52-63` and `api/routers/payments.py:81-88` each work that id out, with `uuid.UUID(int=0)` as the "matches nothing" value. The same sentinel is written six times (`assignments.py:54`, `:61`, `payments.py:84`, `:88`, `scope.py:52`, `:79`).

Fix: `scope.own_ids(session, user) -> tuple[mobilizer_id, agent_id]` and a named `NOBODY = uuid.UUID(int=0)` in `scope.py`.

### B28 - Erased check (second pass)

`privacy.refuse_erased` (`privacy.py:59-61`) exists, and `api/routers/supporters.py` uses it. Three services write the same two lines inline instead: `membership.py:86-87`, `volunteers.py:88-89`, `campaign_volunteers.py:137-138`. Call the function. If importing `privacy` from `membership` makes a cycle, move `refuse_erased` to `services/errors.py` beside `refuse_own_record`.

### B29 - Refusal wording written twice (second pass)

A uniqueness rule is checked before the insert and again when the insert races, and the sentence is typed in both places:

| Sentence | Pre-check | Race handler |
|----------|-----------|--------------|
| "That phone number is already on this campaign's register." | `routers/supporters.py:87` | `api/errors.py:85` |
| "That member already has a live nomination." | `aspirants.py:91` | `api/errors.py:90` |
| "That aspirant already has a workspace." | `aspirants.py:345` | `api/errors.py:93` |
| "That unit already has a target." | `routers/targets.py:83` | `routers/targets.py:98` |
| "That assignment already has a payment." | `routers/payments.py:114` | `routers/payments.py:139` |
| "You already have a live nomination." | `nominations.py:252` | `nominations.py:266` |

Fix: with B10's table in place, give each rule one named constant and use it in both spots. The `targets` and `payments` handlers that catch `IntegrityError` themselves can then let the central handler answer.

Also twice: "This campaign is closed: it is read-only." (`access.py:28`, `privacy.py:47`), and `get_settings().public_url.rstrip('/')` four times (`login_links.py:46`, `privacy.py:246`, `oidc.py:45`, `routers/auth.py:188`), which wants a `Settings.url(path)` method.

### B30 - One-time tokens, three implementations (third pass)

Three features issue a secret, keep only its SHA-256, expire it and spend it once. Each writes the four steps itself:

| Step | Setup token | Login link | Google handoff |
|------|-------------|------------|----------------|
| Hash | `setup.py:41` | `login_links.py:36` | `routers/auth.py:66` |
| Live check with the SQLite zone fix | `setup.py:70-71` | `login_links.py:110-111` | `auth.py:282-285` |
| Void the older ones | `setup.py:58-60` | `login_links.py:52-60`, `:140-144` | - |
| Spend with a guarded UPDATE | `setup.py:78-84` | `login_links.py:132-138` | `auth.py:287-293` |

The models repeat the columns too: `token_hash`, `expires_at`, `used_at` on `SetupToken` (`models/site.py:81-83`) and `LoginInvite` (`models/login.py:25-27`).

Fix: a small `services/tokens.py` with `digest(token)`, `is_live(expires_at, used_at)` and `spend(session, model, row_id)`; a `OneTimeToken` column mixin for the two tables. Security-sensitive, so one change, with `tests/test_setup_api.py`, `tests/test_login_links_api.py` and `tests/test_google_sign_in.py`.

### B31 - Geography listings (third pass)

"Areas of one level that are not retired, by name, optionally under a parent" is written in five places:

- `routers/geography.py:22-91`: four handlers, one per level.
- `routers/party.py:178-207`: four SELECTs in an if-chain (was K3).
- `services/setup.py:87-104`: one table-driven query. This is the short version.
- `services/team_signup.py:74-78` and `services/targets.py:85-89`: centres of a ward.

Fix: one `services/geography.py` `areas(session, level, parent=None)` built like `setup.areas`; the five call it.

### B32 - Two geography importers (third pass)

`seed/reference.py` and `services/imports.py` both upsert counties, constituencies, wards and centres from CSV. They read different file layouts, but the work after parsing is the same and is written twice:

- CSV rows with trimmed headers and values: `reference.py:38-47` and `imports.py:88-108`.
- "Blank or comma-grouped number": `reference.py:56-60` and `imports.py:286-296`.
- Find-or-create per level: `reference.py:111-141`, `:192-210` and `imports.py:201-261`.
- The lookup tables by code: `reference.py:93-109`, `:173-187` and `imports.py:184-191`, repeated at `imports.py:329-335`.

Inside `imports.py` the create / rename / move / restore block is written four times (county `201-212`, constituency `215-230`, ward `233-248`, centre `251-261`), the retire loop three times (`265-278`), and the centre agreement check inline (`173-179`) beside `_agree` (`117-121`), which does the same for the other three levels.

Fix: in `imports.py`, one `_upsert(level, model, have, wanted, parent=None)` and one `_retire(level, have, keep, covered)`. Then let `seed/reference.py` turn the IEBC files into boundary rows and call `imports.import_boundaries`, so there is one writer. The second half changes how first-load matching works (names vs codes), so check it against `tests/test_seed.py` and `tests/test_boundaries.py` before committing to it.

### B33 - Campaign loader and candidate name (third pass)

`NAMED` (`routers/campaigns.py:32-37`) and `CAMPAIGN_NAMES` (`routers/join.py:44-49`) are the same four loader options; `campaign_page.PLACES` (`campaign_page.py:29-34`) is the same with the county chain added. `(candidate.full_name or candidate.username) if candidate else ""` is written at `campaigns.py:45`, `join.py:136` and `campaign_page.py:71`. `Campaign.area` (`models/campaign.py:168-172`) repeats the level-to-attribute map `AREA_FIELD` (`services/campaigns.py:27-31`).

Fix: one `CAMPAIGN_NAMES` beside the model, a `Campaign.candidate_name` property, and one `AREA_FIELD`.

### B34 - Published party posts (third pass)

`services/content.py:31-60` has `_public()` and `upcoming_events`. Two other services query published posts themselves: `candidates.py:138-148` (events naming an aspirant) and `sharing.py:123-144` (events and statements for a county). Fix: make `content._public` public and build both from it.

### B35 - Party member helpers (third pass)

- Ward, constituency, county of a member, built by hand: `routers/account.py:90-92`, `routers/party_members.py:59-65`, `routers/party_volunteers.py:79-81` and again in both CSV exports. The loader chain for it: `account.py:38-41`, `membership.py:427-433`, `volunteers.py:299-308`.
- "The member must be approved": `deps.py:152`, `account.py:59`, `console.py:25`, `admin.py:548-549`, `:606`, `aspirants.py:62`, `branch_officials.py:135`, `nominations.py:243`, `volunteers.py:77`. Nine sites, nine sentences.
- Get-or-create a county's branch: `branches.py:98-103` and `branch_officials.py:77-87`.

Fix: `PartyMember.places` (a dict of the three) and `PartyMember.is_approved` on the model, a `MEMBER_PLACES` loader constant, and `branches.get_or_create(session, county_id)`.

### B36 - Schemas: the same class more than once (third pass)

- `{id, name}` is declared eight times: `admin.py:36` `AdminWardRead`, `content.py:104` `PostCounty`, `content.py:204` `BranchCounty`, `content.py:229` `BranchWard`, `party.py:148` `PartyPlace`, `party.py:155` `MemberPlace` (seven lines apart), `join.py:11` `JoinPlace`, `setup.py:91` `Area`. One `Named` in `schemas/common.py`.
- `{total, items}` three times: `aspirants.py:60`, `party.py:184`, `volunteers.py:39`. One generic `Page[T]`.
- Twin classes: `Switches` and `SwitchesWrite` (`sharing.py:12-21`); `PartyWorkspaceCreate` and `PartyWorkspaceManager` (`party_workspace.py:19-24`), which also extend `BaseModel` instead of `WriteModel`, so unknown fields pass there and nowhere else; `MessageRead` and `PartyMessageRead` share ten fields (`messages.py:51-64`, `party_messages.py:38-52`); `SetupSuperuser` (`setup.py:43-50`) repeats `LoginDetails` (`common.py:76-78`).

### B37 - Schemas: Create/Update pairs (third pass)

In `schemas/content.py` each content type declares its fields twice, once to create and once as `| None = None` to update: Leader (`84-101`), Post (`154-194`), Slide (`317-340`), Issue (`357-374`), Document (`389-402`), AboutItem (`419-432`), Result (`455-472`), Video (`492-509`). About 90 mirrored lines, and a limit changed in one half can be missed in the other. The `sort_order, published, updated_at` tail is repeated on six `AdminRead` classes (`78-81`, `311-314`, `351-354`, `383-386`, `413-416`, `486-489`).

Fix: a `partial(Model)` helper in `schemas/common.py` that builds the update class from the create class with every field optional (pydantic `create_model`), and an `AdminFields` mixin. `PostUpdate` keeps its own class: its `event_date` and `county_id` rules differ. Medium risk because the generated classes feed OpenAPI; `evals/test_frontend_contract.py` covers it.

### B38 - Schemas: field specs retyped (third pass)

- The trim-and-check lambda `AfterValidator(lambda v: plain_text(v).strip())` is written ten times (`content.py:60`, `:61`, `:62`, `:262`, `:264`, `:268`, `:294`, `:516`, `:525`, `candidates.py:18`) although `_short(limit)` (`content.py:293`) builds exactly that type.
- `schemas/privacy.py:13-14` already defines `Line` and `Lines` as `Annotated[str, AfterValidator(plain_text)]`. That is the type B9 asks for; move it to `common.py` and the twelve `_plain` validators go.
- A required https link four times (`content.py:391`, `:400`, `:494`, `:505`); `sort_order` spelt out for leaders (`content.py:89`, `:100`) though `Order` exists (`:298`).
- Password `Field(min_length=8, max_length=128)` three times (`auth.py:58`, `party.py:106`, `setup.py:48`); phone `StringConstraints(strip_whitespace=True, min_length=1, max_length=20)` three times (`party.py:104`, `join.py:36`, `team_signup.py:37`); `Name` defined twice with different limits (`party.py:53` 75, `team_signup.py:12` 150); the SMS length 895 as `BODY_MAX` (`messages.py:12`) and as a bare number (`campaign.py:236`).
- The `ward`, `ward_name`, `registration_centre` alias block on four read models (`campaign.py:65-73`, `99-104`, `131-136`, `190-194`).

### B39 - Models: partial unique indexes (third pass)

Twenty indexes are declared as `Index(name, columns, unique=True, postgresql_where=text(X), sqlite_where=text(X))` with the condition typed twice: `user.py:48-61` (2), `team.py:26-41` (2), `campaign.py:67-73`, `target.py:41-56` (2), `mobilizer.py:24-39` (2), `supporter.py:23-30`, `payment.py:75-90` (2), `content.py:137-144`, `party.py:172-178`, `:207-213`, `volunteer.py:39-45`, `membership.py:34-47` (2), `sms.py:110-124` (2).

Fix: `partial_unique(name, *columns, where)` in `db/base.py`. Each index drops from eight lines to one or two, and the two conditions can no longer drift. Same DDL, so `tests/test_migrations.py` should show no change.

### B40 - Models: the same column per table (third pass)

- "Who did it": `mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None)` 27 times across 14 model files (for example `team.py:67`, `payment.py:112`, `party.py:120`, `sms.py:26`).
- `campaign_id` with `ForeignKey("campaigns.id", ondelete="CASCADE")` 17 times; ten are the identical non-null, indexed form (`team.py:44`, `:88`, `target.py:68`, `mobilizer.py:42`, `event.py:27`, `supporter.py:33`, `assignment.py:31`, `payment.py:93`, `membership.py:50`, `sms.py:19`).
- `stored_files.id` reference six times (`content.py:51`, `:163`, `:178`, `:212`, `:297`, `site.py:45`).
- `sort_order, published, updated_at` on six content models (`content.py:54-56`, `186-188`, `200-202`, `215-217`, `227-229`, `239-241`, `271-273`). `PartyValue` (`220-229`) and `PartyOrgan` (`232-241`) are the same class with a different table name.
- `retired` four times with the same comment (`geography.py:37`, `:59`, `:84`, `:119`); `erased_at` four times (`team.py:73`, `supporter.py:70`, `party.py:133`, `volunteer.py:85`).
- County, constituency, ward foreign keys as a trio on `Campaign` (`campaign.py:85-93`), `Aspirant` (`party.py:220-228`) and `PartyMessage` (`sms.py:46-54`); draft decision fields on both message tables (`sms.py:25-34`, `56-66`).

Fix: column helpers in `db/base.py` (`user_ref()`, `file_ref()`, `campaign_ref()`) and three mixins (`Published`, `Retirable`, `Erasable`). The ward and centre columns stay written out: their `ondelete` rules differ by table (section 6).

One rule is stated in two languages and must be kept in step by hand: live nominations as SQL (`models/party.py:189`) and as a Python set (`services/aspirants.py:31`). Build the SQL from the set.

### B41 - CLI re-implements a service (third pass)

`cli.py:265-275` (`_set_email`) cleans the email, checks who holds it, sets it, audits and commits. `services/admin.py:292-304` (`set_email`) does the same and takes `actor=None`. The two already disagree on the refusal sentence. Every other CLI command calls the service; this one should too.

## 4. KISS items

- **K1 - Two refusal styles.** Routers raise `HTTPException(400, ...)` about 25 times and `Refused` 6 times; services always raise `Refused`, and `api/errors.py` turns it into the same response. Use `Refused`, `NotFound` and `Forbidden` in routers too, so there is one way to refuse.
- **K2 - Explicit 204 responses.** 18 handlers `return Response(status_code=status.HTTP_204_NO_CONTENT)` although the decorator already sets 204; the remaining 204 routes (for example `team.py:76`, `admin.py:111`) return nothing. Drop the explicit returns.
- **K3 - `party.places`** (`party.py:178-207`) is four near-identical SELECTs in an if-chain. A small table of `(parameter, model, parent column)` and one SELECT says the same.
- **K4 - Whole listing for one message.** See B5.
- **K5 - `admin.py` re-reads after every write.** Seven handlers call a service that commits, then `service.user(...)` or `service.campaign(...)` to build the answer. Fine as it is; noted only so nobody "fixes" it into the services, which would couple them to response shapes.
- **K7 - Two fetches to find one row.** `routers/agents.py:127-132` and `routers/assignments.py:84-89` load a row by id, check the campaign, then call a service that loads the same row again inside the caller's area. `scope.require_visible(session, user, Agent, agent_id, "agent", "agents.write")` already does all of it in one call (it answers 403 outside the area where the service answers 404).
- **K8 - Candidate list filtered in Python.** `candidates.py:97-116` loads every listed aspirant and filters seat, county and name in a loop; `_by_slug` (`:119-123`) loads them all to find one. The slug ends in the first eight hex digits of the aspirant id, so one WHERE can narrow it.
- **K9 - Guard aliases.** `Annotated[User, Depends(require("x.write"))]` is written 36 times across the routers. A one-line `may("x.write")` in `api/deps.py` returning that type keeps every alias and drops the noise.
- **K10 - Business rules in a router.** `routers/supporters.py` `register_supporter` (about 50 lines) and `routers/events.py` `invite_to_event` (60 lines) decide wards, centres, audiences and duplicates in the route handler. Every other feature keeps that in `services/`. Moving them is what makes B19 and B21 possible.
- **K11 - The same first line in 55 handlers.** `await require_visible_campaign(session, user, campaign_id)` opens 55 handlers in 15 routers (all 13 in `routers/privacy.py`). A path dependency, `VisibleCampaign = Annotated[Campaign, Depends(...)]`, does it once per router.
- **K12 - Response models filled in by hand.** About a dozen builders copy attributes one by one into a schema that could read them itself: `party_nominations._window` (`49-60`) and `_public` (`63-71`), `payments_in._row` (`27-42`) and `pay.read` (`18-26`, the same seven fields), `team_signup._read` (`37-50`), `party_volunteers._read` (`71-93`), `party_aspirants._read` (`31-50`), `admin.users` (`admin.py:194-208`), the `AreaMember` list (`party_workspace.py:110-121`). `model_validate` plus the two or three computed fields is shorter and cannot forget a field.
- **K13 - Handler pairs that differ only in scope.** `payments_in` campaign confirm/reject (`74-93`) and party confirm/reject (`125-138`); `privacy` campaign requests (`56-84`) and party requests (`219-240`); the three erase handlers in `privacy.py:90-127`.
- **K14 - Generality built for one table.** `PayoutMixin` (`models/payment.py:33`) says it is shared by every payment table; only `Payment` uses it. `payout_flow.PREFIX` has one entry, `ATTEMPT` one alternative (`payout_flow.py:30-31`), and `reconcile.py:135` builds the reference by hand anyway. Either fold the mixin into `Payment` or keep it and use `PREFIX` in `reconcile`.
- **K15 - Statuses as bare strings.** Message and timetable statuses are `"draft"`, `"sent"`, `"declined"`, `"published"` typed as strings (`models/sms.py:25`, `:56`, `models/nominations.py:36` and their services); every other status in the codebase is an enum.
- **K16 - Small repeats.** `config.py:118-130`: two validators with one body, for `payout_provider` and `payin_provider`. `ops.py:174-183` and `:258-264`: the manifest dict twice. `ops.py:255`, `:363`: `Path(settings.upload_dir)` rebuilt though `files.upload_dir()` exists. `subscribers.py:22`: the dialect switch that `db.session.upsert` already wraps. `seed/site.py`: "if the table is empty, add these rows" nine times. `THANKS` twice (`aspirant_site.py:19`, `candidates.py:24`). `models/site.py` imports `hex_colour` from `models/party.py`.
- **K6 - Seed loops.** `seed/demo_aspirant.py:199-217` and `seed/site.py:307-333` insert slides and issues with the same loops. Low value; share only if the seeds are touched for another reason.

## 5. Second pass: corrections to the first pass

The first pass was re-checked against the code. Its line references hold. These points were wrong or short:

- **B6 undercounted and missed the existing answer.** There are 11 sites, not 8: add `team_signup.py:225-242` (`_claim`), `nominations.py:120-127` (`revise`) and `login_links.py:132-137` (`claim`). More important, `services/payout_flow.py:38-57` (`move`) is already a model-agnostic guarded move (`type(row)`, `status.in_(from_)`, refuse on a miss). The fix is to generalise that function, not to write a new one.
- **B5 undercounted.** `text_of` has a third copy inline at `routers/events.py:169`; see B19.
- **B13, withdraw codes.** `privacy.py:242` is not an inline call: it is a second named function, `privacy.new_code`, used by `routers/supporters.py`. So there are two named functions and four inline calls for one idea.
- **B13, phone refusal.** Two more sites: `team_signup.py:118-120` ("Give a phone number like 0712 345678.") and `payments_in.py:161-165` (`_phone`). Eight sites, five wordings.
- **B13, `_county`.** Listed as a small helper; it is one part of the larger B20.
- **B9 missed the setup schema.** See B25.
- **Method wording.** The statement script ran over everything except `seed/`, `models/` and `schemas/`, not only `api/` and `services/`. Fixed in section 1.
- **Coverage.** Of the ten files the first pass named as unread, five are now read (`admin`, `privacy`, `nominations`, `payout_flow`, `team_signup`), along with `accounts`, `team`, `candidates` and `campaign_page`, which it had read only at flagged lines without saying so. Section 1 lists what is still unread.

Checked and left as written: B1 (28 handlers, `admin.py:343-502`), B3 (`deps.py:138` and `:144`, 15 handler calls), B4 (18 checks, 7 importing routers), B8 (`TooLarge` subclasses `Refused` at `files.py:42`), B10 (10 branches).

### Third pass: what the full read changed in earlier findings

- **B17 was wrong about `models/content.py`.** That file already has an `_updated_at()` helper (`content.py:31-39`) and uses it eleven times. The inline copies are `party.py:256-263`, `volunteer.py:86-93` and `nominations.py:44-50`; two more settings rows have the column without `onupdate` (`party.py:64-69`, `site.py:68-73`) and their services set it by hand (`services/party.py:30`, `site.py:46`). The fix is to move the existing helper to `db/base.py`, not to write a mixin.
- **B2 has more sites.** Name-or-phone search also at `console.py:44` and `:60` and `campaign_volunteers.py:99-104`; those three do not escape `%` or `_`, the other three do. A third count-then-page at `party_workspace.py:100-109`, by page number where the others use limit and offset. `dashboard.Filters` (`dashboard.py:53-73`) is a fourth dataclass carrying county, constituency, ward, and `dashboard._in_ward` (`76-83`) and `party_messages._who` (`60-72`) narrow by place the way `membership._query` does.
- **B6 is 14 sites.** Add `assignments.py:188-195`, `setup.py:78-84`, `routers/auth.py:287-293`.
- **B8 is four handlers.** Add `routers/party_nominations.py:249-263`; that router also calls the private `nominations._own_draft` (`:248`).
- **B4 is 19 checks.** Add `routers/sms_callbacks.py:28`.
- **B13 additions.** SHA-256 hex also at `files.py:154` and `imports.py:415`; the uploaded-file URL pattern twice (`rich_text.py:10`, `schemas/content.py:15`); `dashboard.py:186` spells out `full_name or username`; county of a seat has five implementations (`campaign_page.py:53`, `candidates.py:53`, `:61`, `sharing.py:92-104`, `dashboard.py:92-93`).
- **B18.** `setup.test_service` also repeats its own audit block (`setup.py:225-231`, `247-253`).
- **B22 additions.** `geography.py:31-33`, `branches.py:98-99`, `branch_officials.py:78-79` and `:208-210`.
- **B23 additions.** "The party workspace" is looked up at `party_workspace.py:36-37` and again inline at `dashboard.py:238`; "the standalone campaign" at `payments_in.py:156-158` and `campaign_page.py:39-41`.
- **K3** is now part of B31.
- **Seeds.** A demo `PartyMember` is built three ways (`demo.py:181-192`, `demo_party.py:57-67`, `site.py:524-533`); `demo_party._member` should be the one. The Roysambu lookup is written twice (`demo.py:108-113`, `demo_party.py:70-78`).

## 6. Looks alike, leave alone

- `join.py:186-212` and `campaign_volunteers.py:182-212` (known phone, insert, swallow the race). Same shape, different models and columns; a shared helper would need more arguments than it saves lines.
- `aspirants.follow_member` / `volunteers.follow_member` and the two `follow_withdrawal`s. Same names, different rules, and the constant-work property of the withdrawal path depends on each statement being written out.
- The two Paystack `DEAD` sets, and the five separate `RateLimit` buckets in `party.py`.
- `models/event.py:24-34` vs `models/target.py:65-75`, and `models/party.py:103-112` vs `models/volunteer.py:57-65` (ward and centre foreign keys). The `ondelete` rules differ per table; a mixin would hide that.
- `schemas/content.py:174` and `services/content.py:182` both say "A news post has no date or venue.", and `schemas/content.py:532` and `branch_officials.py:214` both say "A term cannot end before it starts." They guard different operations (create vs update, appoint vs end), so both checks are needed.
- The `try: ... except Refused: await session.rollback(); raise` wrapper in `team.py:59-72`, `:92-97`, `admin.py:494-510` and `aspirants.py:346-374`. Four copies of three lines; a context manager would hide the rollback, which is the part a reader needs to see.
- The four provider modules (`email.py`, `sms.py`, `payouts.py`, `payments_in.py`): each has a protocol, a practice provider, a real one and a `get_..._provider`. The shape repeats on purpose and the bodies share nothing.
- `models/enums.py`: forty small enums, no duplication.
- `strategy.py:55-63` and `:79-88`: two supporter counts that look alike but cover different scopes.
- `seed/demo_party.py:81-103` and `seed/demo_aspirant.py:101-143` (`_set_up`): both call the real setup with different content, which is the point.
- Routers and services sharing a verb (`send`, `decline`, `approve`, about 60 names). That is the thin-router layering working as intended, not duplication.

## 7. What is already single-sourced (keep and extend)

- `services/home.py`: one CRUD for seven content models.
- `services/texting.py`: every outgoing text, opt-outs and the log.
- `services/audit.py`: `record` (93 call sites) and `record_if`.
- `api/scope.py`: campaign visibility and area reach for every campaign route.
- `api/deps.py`: `require(action)` and `require_party_role(...)` as the only guards.
- `services/errors.py` + `api/errors.py`: one error shape.
- `schemas/common.py`: `plain_text`, `WriteModel`, `ORMModel`, `LoginDetails`.
- `services/campaign_volunteers.py`: `write_status`, `check_move`, `audit`, reused by `services/volunteers.py`.
- `workspace_site._items`: the route factory B1 asks the console to use.
- `services/payout_flow.py` `move` and `finish`: the guarded update B6 should grow from.
- `services/accounts.py`: `new_login`, `add_member`, `add_mobilizer`, `require_unit`, reused by `admin`, `team`, `team_signup` and two routers.

## 8. Recommended sequencing

1. **B1, B3, B4, B10** - mechanical, low risk, about 235 lines. No behaviour change; run `tests/test_route_guards.py`, `tests/test_admin_api.py`, `tests/test_workspace_site.py`, `tests/test_public_content_api.py`, `evals/test_frontend_contract.py`.
2. **B2, B12, B13, B22, B23, B24, B28** - shared helpers (`services/register.py`, `api/csv.py`, additions to `security.py`, `clock.py`, `sms.py`, `accounts.py`, `db/session.py`). Run the party members, volunteers, aspirants, team and admin API tests.
3. **B7, B8, B9 with B25, B14, B15, B16, B17, B18, B11, B20, B26, B27, B29** - one family per commit.
4. **B21** - one sentence per place rule; the wording changes, so check the frontend first.
5. **B5 with B19, then B6 and B30** last and alone: they touch the send path, the concurrency guard and sign-in tokens.
6. **Third-pass families.** B41 goes in batch 1 (one call). B39 and B40 are one change to `db/base.py` and the model files, checked by `tests/test_migrations.py` showing no schema difference. B36 and B38 ride with B9. B31, B33, B34, B35 are small and independent. B37 and B32 last: they change generated classes and the first-load path.

Two rules keep it from growing back:

1. A router never imports from another router. Shared request helpers live in `api/` modules that define no routes.
2. A new register, content type or draft flow starts from the shared piece (`home`, `register`, `texting`, the route factory) before writing its own.

Total, if every family is done: roughly 1,570 lines out of 26,209 (about 6%): 795 from B1-B18, 251 from B19-B29 and 523 from B30-B41. All three figures are estimates from the spans listed.
