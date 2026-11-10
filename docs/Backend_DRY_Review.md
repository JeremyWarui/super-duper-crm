# Backend DRY / KISS Review

Scope: `backend/src/backend` (26,209 lines, working tree of 2026-11-10). Tests, evals, the migration and the CSV data are out of scope. Comments and docstrings were ignored: every finding below rests on the code itself.

Status: findings only. No backend code was changed by this review. Revised after a second pass (section 5) that read the files the first pass skipped and re-checked the first pass's claims.

## 1. Method

1. `pylint --disable=all --enable=duplicate-code --min-similarity-lines=5` with comments, docstrings, imports and signatures ignored (24 hits).
2. An AST script that strips docstrings and compares every function body, first exactly, then with variable names blanked (13 identical groups, 14 more after renaming).
3. A second AST script that hashes runs of two sibling statements with names and strings blanked, over everything except `seed/`, `models/` and `schemas/` (64 repeated runs).
4. Greps for known idioms (`token_urlsafe`, `HTTP_429`, `tzinfo`, `full_name or username`, phone refusals).
5. Each hit was then read in the source. Files read in full: `api/deps.py`, `api/scope.py`, `api/errors.py`, routers `admin`, `workspace_site`, `party`, `messages`, `party_messages`, `party_members`, `party_volunteers`, `party_aspirants`; services `home`, `content`, `messages`, `party_messages`, `texting`, `membership`, `volunteers`, `aspirants`, `campaign_volunteers`, `payments_in`, `payouts`, `audit`, `errors`, `party`, `site`. Every other file was read only at the lines the tools flagged.

6. Second pass: a script listing every user-facing string of 28+ characters that appears in more than one place (40 strings), then full reads of `services/admin.py`, `accounts.py`, `team.py`, `team_signup.py`, `privacy.py`, `nominations.py`, `payout_flow.py`, `candidates.py`, `campaign_page.py` and routers `events`, `supporters`, `targets`, `mobilizers`, `agents`, `assignments`.

Still not read end to end: `services/ops.py`, `imports.py`, `dashboard.py`, `sharing.py`, `party_workspace.py`, `branch_officials.py`, `setup.py`, `strategy.py`, `targets.py`, `files.py`, `cli.py`, `seed/`, and routers `auth`, `party_nominations`, `privacy`, `campaigns`, `account`, `payments` (read in part). The scripts covered them; a same-idea-different-shape duplicate there can still be missed.

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
| K1-K10 | KISS items (section 4) | - | - | Low | 3 |

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

## 6. Looks alike, leave alone

- `join.py:186-212` and `campaign_volunteers.py:182-212` (known phone, insert, swallow the race). Same shape, different models and columns; a shared helper would need more arguments than it saves lines.
- `aspirants.follow_member` / `volunteers.follow_member` and the two `follow_withdrawal`s. Same names, different rules, and the constant-work property of the withdrawal path depends on each statement being written out.
- The two Paystack `DEAD` sets, and the five separate `RateLimit` buckets in `party.py`.
- `models/event.py:24-34` vs `models/target.py:65-75`, and `models/party.py:103-112` vs `models/volunteer.py:57-65` (ward and centre foreign keys). The `ondelete` rules differ per table; a mixin would hide that.
- `schemas/content.py:174` and `services/content.py:182` both say "A news post has no date or venue.", and `schemas/content.py:532` and `branch_officials.py:214` both say "A term cannot end before it starts." They guard different operations (create vs update, appoint vs end), so both checks are needed.
- The `try: ... except Refused: await session.rollback(); raise` wrapper in `team.py:59-72`, `:92-97`, `admin.py:494-510` and `aspirants.py:346-374`. Four copies of three lines; a context manager would hide the rollback, which is the part a reader needs to see.
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
5. **B5 with B19, then B6** last and alone: they touch the send path and the concurrency guard.

Two rules keep it from growing back:

1. A router never imports from another router. Shared request helpers live in `api/` modules that define no routes.
2. A new register, content type or draft flow starts from the shared piece (`home`, `register`, `texting`, the route factory) before writing its own.

Total, if every family is done: roughly 1,050 lines out of 26,209 (about 4%): 795 from B1-B18 and 251 from B19-B29.
