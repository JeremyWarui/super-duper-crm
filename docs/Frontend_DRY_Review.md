# Frontend DRY / KISS Review

Scope: `frontend/src` (166 files, 15,825 lines, working tree of 2026-11-10, uncommitted edits included). `frontend/tests`, `frontend/scripts`, `ui-kit/` and the build config are out of scope. Comments and docstrings were ignored: every finding below rests on the code itself.

Status: done. Every family (F24 to F42) and every KISS item (K1 to K12) is in the code, in the commits titled "Frontend review batch 1" to "Frontend review batch 5". The rest of this file is the review as written; line references are to the tree before those commits.

## 1. Method

1. `jscpd` over `src` (4 lines, 35 tokens minimum): 75 exact clones, 576 duplicated lines (2.87%).
2. A script listing every string literal and `className` of 24+ characters that appears more than once.
3. Greps for known idioms, each counted (loading lines, raw error paragraphs, role lists, `operational_grain`, `full_name || username`, confirm state, form setters, query shapes in `api/hooks.js`).
4. Every file in `src` read end to end with its real line numbers: `api/`, `app/`, `store/`, `theme/`, `lib/`, `components/` (with `ui/`, `layout/`, `console/`), all of `pages/` (campaign 52, party 10, public 31, member, setup) and the root files. `styles/globals.css` was read only at the classes and tokens the findings name.
5. `tests/apiCalls.js` read at its header, because it limits what `api/hooks.js` may do: a request path must be a string or template literal passed straight to `api`, `download` or `upload`.
6. A script checked 219 of the line references below against the files (text within two lines of the stated line): 0 missed.

Line counts in the "saves" column are estimates from the spans listed, not measured diffs.

## 2. Findings at a glance

| # | Family | Sites | Saves (est.) | Risk | Priority |
|---|--------|-------|--------------|------|----------|
| F24 | Site content hooks written out per model | 27 + 15 hooks | 60 lines | Low | 2 |
| F25 | Mutations that hand-write what `useWrite` does | 22 hooks | 90 lines | Low | 1 |
| F26 | Campaign-scoped reads and query strings | 21 + 6 hooks | 60 lines | Low | 1 |
| F27 | Loading and error states, three ways each | 62 + 15 sites | 40 lines | Low | 1 |
| F28 | Console top-bar tools vs workspace top-bar tools | 2 files | 60 lines | Low | 1 |
| F29 | Party registers: Members, Volunteers, Aspirants | 3 pages | 90 lines | Medium | 2 |
| F30 | "Ask, then do" confirm and reject-with-reason | 7 + 3 sites | 60 lines | Low | 2 |
| F31 | Volunteer sign-up fields | 3 forms | 60 lines | Low | 2 |
| F32 | Public page hero band and rule headings | 7 + 8 sites | 50 lines | Low | 2 |
| F33 | Pressed-button groups beside `FilterPills` | 6 sites | 45 lines | Low | 2 |
| F34 | Public cards: story, date tile, video, quick links | 11 sites | 50 lines | Low | 3 |
| F35 | Labels and option lists retyped | 25+ sites | 50 lines | Low | 1 |
| F36 | Small helpers copied | 60+ sites | 50 lines | Low | 2 |
| F37 | Form plumbing: setters, checkboxes, notices, empty rows | 70+ sites | 70 lines | Low | 3 |
| F38 | `Admin.jsx` keeps its own small kit and its own settings form | 1 file | 80 lines | Low | 2 |
| F39 | Event invite builds its SMS text outside `lib/sms.js` | 1 form | 6 lines | Low | 1 |
| F40 | QR and share-link cards | 4 sites | 30 lines | Low | 3 |
| F41 | Workspace page pieces built by hand | 7 sites | 30 lines | Low | 3 |
| F42 | Transport: four fetches, four error readers | 2 files | 20 lines | Medium | 3 |
| K1-K12 | KISS items (section 4) | - | 70 lines | Low | 3 |

## 3. Findings

### F24 - Site content hooks written out per model

`api/hooks.js:660-812` holds, for nine models (leaders, posts, slides, issues, documents, values, organs, videos, results), one list hook, one save hook and one delete hook each. The nine save hooks are the same five lines with the path changed (`687-692`, `697-702`, `723-734`, `745-750`, `769-780`, `791-796`, `806-811`); the nine delete hooks are one line each. `WORKSPACE_SECTIONS` (`1222-1268`) repeats the trio five more times as nine-line blocks.

The contract test stops a path-building factory, so the saving is smaller than it looks. What it allows:

```js
const saveBy = (add, change) => ({ id, ...body }) => (id ? change(id, body) : add(body));
export const useSaveSlide = () => useSiteWrite(saveBy(
  (body) => api("/admin/party/slides/", { method: "POST", body }),
  (id, body) => api(`/admin/party/slides/${id}/`, { method: "PATCH", body })));
```

Every path stays literal and the "with an id it changes, without one it adds" rule is written once instead of 14 times. The larger fix (one factory per model) needs `tests/apiCalls.js` to learn a table of models first; only then is it worth doing.

### F25 - Mutations that hand-write what `useWrite` does

`useWrite(mutationFn, ...keys)` (`hooks.js:71`) is used 48 times. Twenty-two more hooks write the same thing out with `useMutation`:

- **Nine admin hooks** (`554-618`, `936-955`, `1120-1127`: set active, set email, rename, add member, remove member, grant role, revoke role, link member) build `useAdminInvalidator()` then `useMutation({ mutationFn, onSuccess: invalidate })`. `useAdminInvalidator` invalidates `["admin"]`, and `useInvalidator("admin")` invalidates `["admin"]` too. Each is `useWrite(fn, "admin")`.
- **Seven "refresh even when refused" hooks** use `onSettled`: `210`, `218`, `232`, `242`, `312`, `585`, `1182`. One `useWrite.settled(fn, ...keys)` (or an option) covers them.
- **Six "the answer is the new cache" hooks** use `setQueryData`: `202`, `865`, `873`, `1312`, `1355` and `useMine` (`1482`). `useMine` is already the helper; name it `useReplace(fn, key)` and use it for all six.
- `useSaveBranch` (`849-860`), `useAppointOfficial` and `useEndTerm` (`1450-1469`) invalidate fixed key lists by hand; they are `useWrite(fn, "office-branches", "public-branches", "branch-officials")`.

Watch: the admin hooks return the invalidation promise from `onSuccess`, so `isPending` stays true until the lists have refetched. `useWrite` does not return it. Make `useInvalidator` return `Promise.all(...)` and `useWrite` return that, or buttons in the console re-enable a moment early.

Tests: `tests/hooks.test.jsx`, `tests/admin.test.jsx`, `tests/payments.test.jsx`, `tests/contract.test.js`.

### F26 - Campaign-scoped reads and query strings

Twenty-one queries are `useQuery({ queryKey: [key, campaignId], queryFn, enabled: !!campaignId })` (`hooks.js:21-61`, `154`, `176`, `251`, `265`, `422`, `1175`, `1336`, `1352`, `1363-1367`, `1527`, `1585`, `1608`). One helper keeps every path literal:

```js
const useFor = (key, id, queryFn, more) => useQuery({ queryKey: [key, id], queryFn, enabled: !!id, ...more });
export const useTargets = (id) => useFor("targets", id, () => api(`/targets/?campaign=${id}`));
```

Query strings are built two ways. `memberQuery` (`971-977`) drops blank values and is used by eight hooks that have nothing to do with members (dashboard, audit, admin users). Six others build theirs by hand: `usePublicPosts` (`648`), `usePublicCandidates` (`1133`), `useAssignments` (`254`), `useAdminUsers` (`511`), `useSetupAreas` (`1385`), and `usePartyPlaces` (`821-824`), which is a four-way `if` chain that one `memberQuery({ county, constituency, ward })` call replaces. Rename it `queryOf` and use it everywhere.

### F27 - Loading and error states, three ways each

Loading:

- `LoadingText` (`components/ui/loading-text.tsx`): 14 uses.
- `KitLoading` (`pages/campaign/WsHeader.jsx:3`): the same paragraph under another name, 20 uses.
- The raw `<p className="text-muted-foreground">Loading…</p>`: 21 sites (for example `DataRequests.jsx:118`, `PayDialog.jsx:113`, `party/Website.jsx:301`, `:431`, `party/Branches.jsx:188`, `:228`, `member/Account.jsx:166`, `:247`, six public pages).
- `<div className="site-container py-12 text-muted-foreground">Loading…</div>`: 7 sites.

Errors: `ErrorText` has 141 uses, and 15 sites still write `role="alert"` and `error.message` by hand: `member/Account.jsx:248`, `:365`, `party/Branches.jsx:229`, `public/Branch.jsx:16`, `Candidate.jsx:155`, `Candidates.jsx:65`, `Events.jsx:59`, `Issue.jsx:18`, `JoinParty.jsx:91`, `Leadership.jsx:36`, `News.jsx:149`, `Post.jsx:65`, `Results.jsx:82`, `SetPassword.jsx:38`, `TeamSignup.jsx:54`.

Six public pages open with the same two guards (`Issue.jsx:17-18`, `Post.jsx:64-65`, `Candidate.jsx:154-155`, `Branch.jsx:15-16`, `JoinParty.jsx:89-91`, `Account.jsx:364-365`).

Fix: delete `KitLoading`; use `LoadingText` and `ErrorText` at every raw site; add `PageState({ query })` in `pages/public/` that returns the loading or error block inside `site-container`, or null, for the six guard pairs.

### F28 - Console top-bar tools vs workspace top-bar tools

`components/layout/ConsoleTools.tsx` and `pages/campaign/WorkspaceShell.tsx` each build search, a bell and help for the top bar:

- `PANEL`, `ICON_BUTTON`, `ROW`: byte-identical constants (`ConsoleTools.tsx:10-12`, `WorkspaceShell.tsx:78-80`).
- Help panel: `ConsoleTools.tsx:96-116` and `WorkspaceShell.tsx:192-210`. Same button, same "Need help?", same call and email rows; only the lead sentence differs.
- Bell: `ConsoleTools.tsx:70-93` and `WorkspaceShell.tsx:167-189`. Same button, badge, empty line and link rows.
- Ctrl K listener: `ConsoleTools.tsx:23-29` and `WorkspaceShell.tsx:87-93`.
- Result list: `ConsoleTools.tsx:46-57` and `WorkspaceShell.tsx:130-141`.

Fix: `components/layout/TopBarTools.tsx` with `HelpPanel({ id, lead })`, `BellPanel({ id, notes })` (notes are `{ key, text, to }`), `HitList({ hits, onPick })` and `useHotkeyK(fn)`. Each side keeps its own search box and its own source of notes.

Tests: `tests/consoleTopBar.test.jsx`, `tests/app.test.jsx`.

### F29 - Party registers: Members, Volunteers, Aspirants

The three officer pages are one page three times:

- State, filters, the `set` wrapper that resets the offset, totals and CSV export: `party/Members.jsx:113-146` and `party/Volunteers.jsx:93-116` (jscpd: 61 lines).
- `?open=` and `?status=` handling: `Members.jsx:120-130` and `Aspirants.jsx:326-336`, identical, with the `Linked` component beside each (`Members.jsx:108-111`, `Aspirants.jsx:315-318`).
- The reason box and one button per allowed move: `Members.jsx:75-100` and `Aspirants.jsx:167-192`.
- Erase with a second press: `Members.jsx:36-46` and `Volunteers.jsx:73-83` (see F30).
- The status and place selects, the header with a count, the table card, the pager.

Fix: a `useRegister(useList, filters)` hook returning `{ items, total, offset, setOffset, set, exportCsv, exportError }`, a `useLinkedRecord(setStatus)` hook for the two query parameters, and a `MoveButtons({ moves, move, id, needsReason })` component. Each page keeps its columns and its detail fields.

Medium risk only because these pages carry the most tests: `tests/members.test.jsx`, `tests/volunteers.test.jsx`, `tests/aspirants.test.jsx`, `tests/nominations.test.jsx`.

### F30 - "Ask, then do" confirm and reject-with-reason

The same small state machine (a button, then a question with Yes and Cancel) is written seven times: `Admin.jsx:73-97` (`Danger`), `components/EraseButton.jsx:5-19`, `party/Members.jsx:29-50`, `party/Volunteers.jsx:72-84`, `campaign/Privacy.jsx:88-96`, `member/Account.jsx:227-235`, `campaign/Team.jsx:75-82`.

A reason box with a confirm and a back button is written three times: `PaymentsInTable.jsx:54-60`, `campaign/Signups.jsx:50-76`, `SmsParts.jsx:21-29` (`DeclineForm`).

Fix: `components/ui/confirm.tsx` with `Confirm({ label, question, yes, variant, pending, onConfirm })`; `EraseButton` and `Danger` become two-line presets of it. `DeclineForm` moves to the kit as `ReasonForm({ label, placeholder, min, yes, no })` and serves all three reject sites.

### F31 - Volunteer sign-up fields

Profession (with "other"), ways to help (with "other") and preferred contact are written three times: `member/Account.jsx:78-110`, `public/JoinParty.jsx:176-206`, `public/Candidate.jsx:63-95`. The rule for a complete answer is written twice (`JoinParty.jsx:77-83`, `Candidate.jsx:35-38`), the body that clears the "other" text when it is not chosen once (`JoinParty.jsx:107-114`) and not at all in the other two.

Fix: `components/VolunteerFields.jsx` taking `value`, `onChange` and a `pills` switch for the two checkbox looks, with `volunteerReady(value)` and `volunteerBody(value)` beside it. The three forms keep their own names, places and consent boxes.

Tests: `tests/account.test.jsx`, `tests/joinParty.test.jsx`, `tests/candidates.test.jsx`, `tests/aspirantSite.test.jsx`.

### F32 - Public page hero band and rule headings

Seven pages open with a coloured band holding breadcrumbs, an optional kicker, the title and a lead: `Candidates.jsx:39-43`, `Events.jsx:46-49`, `Leadership.jsx:26-32`, `Manifesto.jsx:17-22`, `Vie.jsx:58-66`, `Results.jsx:64-70`, `Issue.jsx:39-45`. `PageHead.jsx` is the plain version of the same thing.

The title's class `text-[clamp(40px,5vw,64px)] leading-none` is typed on seven pages; it is the `text-page` token (`styles/globals.css:184`), which `PageHead` and `Issue` already use.

Fix: `PageHero({ tone, crumbs, kicker, title, lead, children })` beside `PageHead`.

Two more headings are typed out: `rule-top font-display text-[32px] font-extrabold` eight times (`About.jsx:83`, `Candidate.jsx:202`, `:208`, `:219`, `Leadership.jsx:50`, `Manifesto.jsx:32`, `:50`, `Vie.jsx:72`), and the workspace card title `text-card-title font-bold` 42 times while `CardTitle` (`components/ui/card.tsx:39`) has no caller. Add `RuleHead` to `typography.tsx` and use `CardTitle`.

### F33 - Pressed-button groups beside `FilterPills`

`FilterPills` (`components/ui/tabs.tsx:63`) is the kit's group of `aria-pressed` buttons. Six places build their own:

- `public/Candidates.jsx:36`, `:57-62` and `public/Results.jsx:61`, `:74-79`: the same `pill` function and the same loop (jscpd: 17 lines).
- `campaign/PartyFeed.jsx:46-53`, `components/PayDialog.jsx:13-21` (`Choice`), `campaign/RegisterSupporterForm.jsx:67-74`, `Admin.jsx:962-979` (`Choices`).

`public/Candidate.jsx:192-196` hand-rolls a tab list although `Tabs look="underline"` exists and `member/Account.jsx` uses it.

Fix: give `FilterPills` a `look` (`capsule`, `ink`, `tint`) and use it at the six sites; use `Tabs` on the candidate page.

### F34 - Public cards

- Story card (photo, kicker, title, date): `News.jsx:54-59` and `Post.jsx:32-37`, identical.
- Side story row: `Home.jsx:237-244` and `News.jsx:30-37`.
- Date tile (month or weekday over the day number): `campaign/Events.jsx:32-39`, `public/Home.jsx:265-268`, `public/Events.jsx:23-26`.
- Video card: `Home.jsx:199-208` and `AspirantHome.jsx:145-151`.
- Quick-links aside: `Home.jsx:44`, `:54-60` and `AspirantHome.jsx:34`, `:42-48`.
- `Photo` is defined twice with the same body: `Home.jsx:177` and `story.jsx:7`.
- The kicker `text-meta font-extrabold uppercase tracking-[0.08em] text-primary` is typed seven times; `StoryMeta` (`typography.tsx:39`) is that element and has no caller.

Fix: `story.jsx` gains `StoryCard`, `StoryRow`, `DateTile`, `VideoCard` and `QuickLinks`; `Home.jsx` imports `Photo`.

### F35 - Labels and option lists retyped

| What | Where it is defined | Retyped at |
|------|--------------------|------------|
| Seat labels | `party/helpers.js:133` `SEAT_LABEL` | `public/Candidates.jsx:11` and `public/Candidate.jsx:20` (`SEAT_NAME`, twice), `public/Results.jsx:85` (`SEATS.find`) |
| Seats and their areas | `party/helpers.js:125`, `:134` `SEAT_AREA` | `setup/Setup.jsx:20` retypes `SEATS`, then does `SEATS.find(...)[2]` at `:57`, `:69`, `:116` |
| Agent steps | - | `campaign/Agents.jsx:14`, `campaign/MyCentre.jsx:12` |
| Mobilizer / Agent | `campaign/helpers.js:82` `ROLE_LABEL` | `campaign/Privacy.jsx:16`, `campaign/Signups.jsx:18`, inline at `Assignments.jsx:40` |
| Member status tone | `party/helpers.js:24` `STATUS_TONE` | `campaign/Members.jsx:13` (which imports `STATUS_LABEL` from there) |
| Volunteer status | `party/helpers.js:75-87` | `campaign/Volunteers.jsx:19-20`, inline at `member/Account.jsx:138`. "Inactive" is `bad` in one and `stone` in the other |
| Support levels | - | `InviteForm.jsx:16`, `RegisterSupporterForm.jsx:12`, `Supporters.jsx:16` |
| Assignment status | - | `Assignments.jsx:15`, `:43`, `MyCentre.jsx:51` |
| Empty place | `party/helpers.js:3` `NO_PLACE` | `Aspirants.jsx:41`, `:70`, `party/Messages.jsx:38`, `Setup.jsx:122` |
| Party-only settings | `api/hooks.js:633` `PARTY_FIELDS` | `Admin.jsx:776` `PARTY_ONLY` |
| "Helps with" and profession text | - | `campaign/Volunteers.jsx:24-26`, `party/Volunteers.jsx:25-28`, `member/Account.jsx:132`, `:146` |
| Numbered lines of a text | - | `Manifesto.jsx:8`, `Vie.jsx:46` (identical), `Issue.jsx:10` |
| SMS body limit 895 | - | `SmsParts.jsx:15`, `InviteForm.jsx:41`; 918 at `lib/sms.js:15` |
| Attendance rule sentence | - | `RecordForm.jsx:18`, `AttendanceCard.jsx:36`, two wordings |

Fix: one `lib/labels.js` for the label maps and option lists (the party ones move there from `party/helpers.js`, see K4), `linesOf(text)` in `lib/format.js`, `BODY_MAX` in `lib/sms.js`.

### F36 - Small helpers copied

| Helper | Copies | Fix |
|--------|--------|-----|
| "Candidate or manager" | Six named lists (`Agents.jsx:15`, `InviteForm.jsx:18`, `Signups.jsx:19`, `Supporters.jsx:18`, `Volunteers.jsx:21`, `Payments.jsx:128`) and three inline checks (`helpers.js:131`, `Targets.jsx:92`, `CampaignModal.jsx:44`) | `isLead(role)` in `campaign/helpers.js` |
| Units are centres, and the word for a unit | `operational_grain === "centre"` nine times; "ward"/"centre" worked out again in `Mobilizers.jsx:33-34`, `Overview.jsx:75`, `Targets.jsx:99`, `Units.jsx:42`, `AreaPicker.jsx:12`, `MobilizerForm.jsx:31`, `AssignMobilizerForm.jsx:13` | `unitOf(campaign)` returning `{ byCentre, noun, Noun }` |
| `full_name \|\| username` | 8 sites (`App.jsx:117`, `Portal.jsx:68`, `Team.jsx:31`, `:68`, `:86`, `:89`, `AreaPicker.jsx:34`, `ManagerForm.jsx:25`) | `displayName(user)` in `lib/format.js` |
| First name | `Candidate.jsx:27`, `:141`, `:177`, `AspirantHome.jsx:16`, `Chooser.jsx:31`, `SiteHeader.tsx:28` | `firstName(name)` in `lib/format.js` |
| Area and county without a repeat | `Candidate.jsx:106`, `Candidates.jsx:21` | one `whereOf(c, sep)` |
| Office contact "a or b" | `Account.jsx:194`, `public/Privacy.jsx:26-27` (worked out twice in one expression) | `contactOf(site)` |
| Office names of a login | `Portal.jsx:48-52`, `Chooser.jsx:19` | export `officeOf` |
| Pages a login may open | `Portal.jsx:41`, `:82` | one `pagesFor(user)` |
| Distinct wards from targets | `campaign/helpers.js:120-127`, `campaign/shell.js:49-56` | `useWardOptions` only; the shell sorts its result |
| Targeted centres of a ward | `RegisterSupporterForm.jsx:27-30`, `Supporters.jsx:56-60` | `useTargetedCentres(campaignId, ward)` |
| Member search once two letters are typed | `Admin.jsx:536-537`, `party/Branches.jsx:121-122`; neither stops the request for a shorter text | `useMemberSearch(q, filters)` with `enabled` |
| Absolute link from a path | `window.location.origin` 8 times | `linkTo(path)` |
| Thousands separators | `formatNumber` uses the browser's locale (`lib/format.js:5`); 4 sites call `toLocaleString("en-KE")` themselves (`party/Website.jsx:159`, `Results.jsx:42`, `:47`, `About.jsx:62`) | `formatNumber` uses `en-KE`; the 4 sites call it |
| Timestamps | `new Date(x).toLocaleString()` at `AuditTrail.jsx:39`, `ReferenceData.jsx:104`, `Health.jsx:13`, `Payments.jsx:145`, in the browser's zone | `formatDateTime` in Nairobi time, beside `formatDate` |
| A link page | `public/Unsubscribe.jsx:14-28` is `LinkAction` written out with a primary button | `LinkAction` takes `variant` |

### F37 - Form plumbing

- `const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })` is written 14 times, some with the stale-closure form and some with the updater form. One `useForm(initial)` in `lib/` returning `[form, set, patch, reset]`.
- 22 checkboxes; 14 carry `size-[18px] accent-primary` inside a hand-built label with one of five gap and alignment variants. One `Check({ checked, onChange, children })` in `components/ui/input.tsx`.
- The amber notice box (`border-[#F2D98A] bg-warn ... text-warn-foreground`): `Payments.jsx:86`, `ReleaseForm.jsx:37`, `Team.jsx:57`, `SendError.jsx:10`. One `Notice`.
- The green result line `role="status" ... font-semibold text-primary`: `Health.jsx:35`, `:51`, `:69`, `ExportPanel.jsx:30`, `Admin.jsx:922`, and "Saved." four more times. One `StatusText`.
- The empty table row `<TR><TD colSpan={n} className="text-muted-foreground">`: 17 sites, each with a hand-counted `colSpan` (`Supporters.jsx:110` says 6 and `Signups.jsx:119` says 7 for tables whose column count changes). `EmptyRow` with `colSpan={99}`.
- The screen-reader-only column head: 9 sites. `TH` takes `hidden`.
- `Health.jsx`: `TestSend` (`24-39`), `TestEmail` (`42-55`) and `SignIn` (`58-74`) are the same button, result line and error three times.

### F38 - `Admin.jsx` keeps its own small kit and its own settings form

`components/Admin.jsx` is 1,180 lines, the largest component by a factor of two.

- Local stand-ins for kit pieces: `Btn` (`54-58`) is `Button shape="rounded" size="sm"`; `Heading` (`69`) is `CardTitle`; `Choices` (`962-979`) is `FilterPills` with another look; the totals band (`1053-1067`) is a fourth figure row beside `StatTiles`.
- `handOut` (`1022-1023`) repeats the `onPassword` callback four lines above it (`1011-1012`).
- The site settings are edited by two forms with two field lists: `PartyForm` (`741-931`, fields `PARTY_TEXT` at `741-754`, one `Field` + `Input` block per text area) and `campaign/Settings.jsx` (`LINES` at `11-22`, rendered by `ConfigFields`). The length limits exist only in the second. `PartyForm` should render through `ConfigFields` from one shared `SITE_FIELDS` list.
- A colour is entered three ways: plain boxes (`Admin.jsx:821-834`), a box with a swatch (`Settings.jsx:51-58`), a picker with the contrast check (`Setup.jsx:135-146`). The server enforces the contrast rule on all three; `Swatch` is the one that tells the user, so move it to `components/` and use it in all three.

Fix: split the file by tab into `components/console/` (`Campaigns.jsx`, `Logins.jsx`, `SiteSettings.jsx`), where `Health`, `AuditTrail`, `ExportPanel` and `ReferenceData` already live.

### F39 - Event invite builds its SMS text outside `lib/sms.js`

`campaign/InviteForm.jsx:28-30` builds `message.trim() + FOOTER`, counts parts and decides readiness itself; `:40-41` writes the hint and the 895 limit again. `composed(body)` (`lib/sms.js:13`) and `MessageField` (`SmsParts.jsx:12`) do all of it for the two message pages. The invite form does not check the six-part limit that `composed().fits` checks.

Fix: use `MessageField` and `composed` in `InviteForm`.

### F40 - QR and share-link cards

- The printable QR block and the footer under it: `CampaignLinkModal.jsx:21-34` and `QrModal.jsx:17-29`.
- A link with its QR code, Copy, Replace and the "replacing stops the old one" note: `Signups.jsx:33-45` and `Recruitment.jsx:34-46`.

Fix: `QrPrint({ title, link })` and `LinkCard({ url, qrTitle, onReplace, note })` beside `ShareLink.jsx`.

### F41 - Workspace page pieces built by hand

- Twenty campaign pages use the slotted header; `Settings.jsx:73-76`, `Website.jsx:62-65` and `Recruitment.jsx:26-29` build their own `h1` and lead, so those three do not get the sticky frosted header.
- The dark figure band: `Overview.jsx:27-35` and `Targets.jsx:77-84`.
- The coverage card: `Agents.jsx:29-45` and `Mobilizers.jsx:12-28`.

### F42 - Transport

`api/client.js` has three functions that each read the token, build the `Authorization` header and call `fetch` (`17-27`, `45-48`, `66-74`), and three ways of reading a refusal: `api` takes `detail` or the first field's first message (`35-36`), `download` and `upload` take only `detail` (`52`, `77`), and only `api` keeps `code`. `store/auth.js:25-33` is a fourth `fetch` with a fourth reader.

Fix: one `send(path, init, { anonymous })` that adds the header and runs `expireOn401`, and one `refusal(res, data, fallback)` that builds the error with `status` and `code`. `api`, `download` and `upload` become the three ways of preparing the body and reading the answer. Sign-in can call `api("/auth/login/", { anonymous: true })` only if the import cycle between `client.js` and `auth.js` is broken first; leave it if not.

Medium risk because every request passes through it. `tests/client.test.js`, `tests/auth.test.js`.

## 4. KISS items

- **K1 - Kit code nobody calls.** `components/ui/popover.tsx` (the whole file; `@radix-ui/react-popover` and `@radix-ui/react-dropdown-menu` have no other user), `CardTitle`, `CardDescription`, `KpiValue` (`card.tsx:39-50`), `StoryMeta` (`typography.tsx:39`), the exported `badgeVariants`, `buttonVariants`, `cardVariants`, `fieldVariants`, and `useWards` (`hooks.js:18`). The key `"admin-branches"` is invalidated at `hooks.js:855` and `:1452` and read by no query. Use `CardTitle` and `StoryMeta` (F32, F34); delete the rest.
- **K2 - `shape="rounded"` on 186 of 253 buttons.** Every signed-in screen passes it. Let `AppLayout` set the default through context, as `.app-shell` already does for cards.
- **K3 - `WsHeader.jsx`.** Three lines: a re-export of `SlottedHeader` and `KitLoading`. Twenty files import a header through an alias of an alias.
- **K4 - Shared code that lives in a page folder.** `pages/campaign/LoginFields.jsx` is imported by `setup/Setup.jsx`, `components/Admin.jsx` and `party/Aspirants.jsx`. `pages/party/helpers.js` is imported by ten files outside `pages/party` (campaign, member, public and `components/Admin.jsx`). `pages/party/Website.jsx` exports the editor that `campaign/Website.jsx` uses; `pages/party/Portal.jsx` exports `PartyShell` to `components/Admin.jsx`; `components/LinkAction.jsx` imports `pages/public/PageHead`. Move each shared piece to `lib/` or `components/`.
- **K5 - Two import spellings.** 633 imports use `@/`, 29 use `../../`. `campaign/MyCentre.jsx:7` and `:9`, and `public/Vie.jsx:10-11`, import `lib/format` twice by both paths.
- **K6 - Route wrappers that only pass a parameter.** `Gate.jsx:145-159` has four components whose whole body is `<X code={useParams().code} />`. `CandidateWithdraw` and `Unsubscribe` read their own parameter; the four pages can too.
- **K7 - A hand-drawn icon.** `Login.jsx:16-45` draws the eye and eye-off paths; `lucide-react` (already a dependency) ships `Eye` and `EyeOff`.
- **K8 - An eleven-key list.** `useSiteWrite` (`hooks.js:671-681`) names `"site"` and ten `"public-..."` keys. A predicate on keys that start with `public-` cannot forget the next one.
- **K9 - Variables that are returned on the next line.** `public/Candidate.jsx:46-52` (`const thanks = ...; return <div>{thanks}</div>`) and `:54-101` (`const form = ...; return form`); `public/Home.jsx:262-272` is a block-bodied arrow holding only a `return`.
- **K10 - Colours typed as hex in class names.** `#CFE0D5` (muted text on the primary colour) 15 times, `#F2D98A` 4 times, `#C9CDCB` and `#DDE3DF` twice each. `--text-on-dark-muted` exists; add `--text-on-primary-muted` and a warn border token.
- **K11 - "Today" in the browser's zone.** `WorkspaceShell.tsx:32` (`daysTo`) and `campaign/Privacy.jsx:73` compare against the device's date; everything else uses `nairobiDate()`.
- **K12 - Two attendance forms, one rule.** `RecordForm.jsx` (dialog) and `AttendanceCard.jsx` (phone) both check "reached above zero, attended not above reached". Keep both screens; share `attendanceOk(reached, attended)` and one sentence.

## 5. Looks alike, leave alone

- `campaign/Messages.jsx` and `party/Messages.jsx`: what is left differs (wards vs audience and place, send vs send for approval).
- The message hooks for campaigns and for the party, the `ERASE` map (`hooks.js:1588-1592`), and the campaign-or-party ternaries in `useDataRequests`, `usePaymentsIn` and `useDecidePaymentIn`: the contract test needs every path written out.
- The twelve small campaign dialogs (`MarkPaidForm`, `DeclinePaymentForm`, `NotSentForm`, `RecordForm`, ...): each is already `Dialog` + `ErrorText` + `FormActions`. A generic form dialog would need render props for the one part that differs.
- `copy.js` `PARTY` and `ASPIRANT`, and the route tables in `Gate.jsx`: two parallel lists on purpose.
- `WORKSPACE_SECTIONS` and the party `SECTIONS` table: configuration, not logic.
- `Home.jsx` and `AspirantHome.jsx`: the second already composes the first's sections.
- `Crumbs` and the breadcrumb in `CrmTopBar`: two looks, two places.
- `useAdminUsers` beside `useAdminUserPages` (`Admin.jsx:999-1000`): the pickers and the tab count need every login, the list pages through them.
- The `Summary` and `Tiles` functions that only build the array for `StatTiles`.
- `text-small text-muted-foreground` (108 times) and the other two-class pairs: utilities doing their job, not components waiting to be extracted.
- `holderOf` in `party/Branches.jsx:42` and in `campaign/helpers.js:27`: same name, different things.

## 6. What is already single-sourced (keep and extend)

- `lib/format.js`, `lib/sms.js`, `lib/email.js`, `lib/username.js`, `lib/draft.js`, `lib/usePanel.ts`, `lib/useClipboard.js`, `lib/useShowMore.js`, `lib/home.js`.
- `components/ui/`: `Button`, `Card`, `Badge`, `Table`, `Dialog`, `Field`, `FilterSelect`, `FilterPills`, `ErrorText`, `FormActions`, `StatTiles`, `Pager`, `LoadMore`, `InviteDialog`.
- `components/PlaceCascade.jsx`, `MemberSearch.jsx`, `ConfigFields.jsx`, `SmsParts.jsx`, `PaymentsInTable.jsx`, `DataRequests.jsx`, `PayDialog.jsx`, `LinkAction.jsx`, `RichText.jsx`, `RichTextView.jsx`.
- `api/hooks.js` `useWrite` (48 uses) and `api/client.js` `expireOn401`.
- `pages/party/Website.jsx`: one field-driven editor for nine content types and two installations.
- `components/layout/AppLayout.tsx` + `AppPage.tsx`: one shell for the console, the party portal and the workspace.
- `copy.js`: the only place the party and aspirant wordings differ.

## 7. Recommended sequencing

1. **F25, F26, F27, F28, F35, F39** - mechanical, about 310 lines. Run `tests/hooks.test.jsx`, `tests/contract.test.js`, `tests/consoleTopBar.test.jsx`, `tests/messages.test.jsx` and the page tests of each file touched.
2. **F30, F31, F32, F33, F36, F38** - new shared pieces (`Confirm`, `VolunteerFields`, `PageHero`, the `FilterPills` looks, the helper table, the console split), one family per commit.
3. **F29** alone: the three register pages, with their four test files run before and after.
4. **F24, F34, F37, F40, F41 and the KISS items** as the files are next opened. K4 (move shared code out of page folders) goes first among them, since F31, F35 and F38 put their new pieces in `lib/` and `components/`.
5. **F42** last and alone: every request passes through it.

Two rules keep it from growing back:

1. A page folder imports from `lib/`, `components/` and `api/`, never from another page folder.
2. A new status line, loader, confirm, notice or button group starts from the kit piece. A page that needs a look the kit lacks adds the look to the kit.

Total, if every family is done: roughly 1,070 lines out of 15,825 (about 6.8%): 1,001 from F24-F42 and 70 of dead code from K1. Both figures are estimates from the spans listed.

## 8. The earlier review (F1 to F23)

The earlier draft of this file listed 23 families and marked all of them resolved. Their single-source pieces exist and are in use (section 6). Four of its claims do not hold against the tree:

- **F15 (inline error paragraph)** said no stray sites remain. Fifteen remain (F27).
- **F8 (SMS pages)** covered the two message pages; `InviteForm.jsx` still builds its own text (F39).
- **F21 (top bars)** merged the bars; the tools inside them are still written twice (F28).
- **F20 (hooks)** said the invalidators keep no lists. `useSiteWrite` keeps eleven keys and `useOfficialsChanged` four (K8, F25).

| # | Family | Single source today |
|---|--------|---------------------|
| F1 | Two UI kits | `components/ui/*.tsx` |
| F2 | KES formatters | `lib/format.js` `formatKES` |
| F3 | Date formatters | `lib/format.js` `formatDate`, `formatDay`, `nairobiDate` (timestamps: F36) |
| F4 | `initials` | `lib/format.js` |
| F5 | Email and username checks | `lib/email.js`, `lib/username.js` |
| F6 | Place cascader | `components/PlaceCascade.jsx` |
| F7 | Login fields | `pages/campaign/LoginFields.jsx` (placement: K4) |
| F8 | SMS pages | `components/SmsParts.jsx`, `lib/sms.js` (invite form: F39) |
| F9 | Click-outside panel | `lib/usePanel.ts` |
| F10 | Clipboard | `lib/useClipboard.js` |
| F11 | Form footer | `components/ui/form-actions.tsx` |
| F12 | KPI tiles | `components/ui/stat-tiles.tsx` (dark band, console totals: F38, F41) |
| F13 | Filter selects | `components/ui/input.tsx` `FilterSelect` |
| F14 | Pagination | `components/ui/pager.tsx`, `load-more.tsx` |
| F15 | Error paragraph | `components/ui/error-text.tsx` (15 stray: F27) |
| F16 | Link pages | `components/LinkAction.jsx` (`Unsubscribe`: F36) |
| F17 | Gate notices | `components/SignedInNotice.jsx` |
| F18 | Status maps | `pages/party/helpers.js` (campaign copies: F35) |
| F19 | API root and 401 | `api/base.js`, `api/client.js` `expireOn401` (F42) |
| F20 | Hooks | `api/hooks.js` `useWrite` (F24, F25, F26) |
| F21 | Top bars | `components/layout/CrmTopBar.tsx` (tools: F28) |
| F22 | Member search | `components/MemberSearch.jsx` |
| F23 | Config-driven fields | `components/ConfigFields.jsx` (console settings: F38) |
