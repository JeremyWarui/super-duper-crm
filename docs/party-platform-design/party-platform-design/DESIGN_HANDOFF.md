# Party Platform — Design Handoff

Licensable "operating system for political parties" (Kenya). One codebase; each party gets its own branded copy (website + CRM + candidate workspaces + member/field apps). The vendor (us) runs the platform; each party owns its data.

The `screens/` folder holds the mockups as `.dc.html` files (Design canvas format). Treat them as **visual and behavioural reference**: layout, copy, states and interactions. They are not production code — rebuild them in the app stack. Each file's markup is plain HTML with inline styles; the `<script type="text/x-dc">` block at the bottom shows the screen's state and interaction logic. Values in `[brackets]` are placeholders, never real data.

## Design tokens

| Token | Value | Use |
|---|---|---|
| Party primary | `#0B5D3B` | buttons, active nav, links (configurable per party) |
| Accent | `#F2B705` | highlights, secondary CTAs (text on it: `#13201A`) |
| Ink | `#13201A` | text, dark panels, CRM sidebar |
| Ground (public) | `#F6F5F0` | public site background |
| Ground (app) | `#F3F4F2` | CRM / workspace background |
| Muted text | `#4B5751` | secondary text (passes 4.5:1) |
| Border | `#E1E4E2` / `#DEDBD0` | cards |
| Success / warn / danger pills | `#E3F1E8/#0B5D3B`, `#FFF3CC/#6B5100`, `#FCE4E2/#9A1C12` | status |
| Vendor console | `#141826` sidebar, `#2F5BEA` primary | our own brand, separate from parties |
| Fonts | Bricolage Grotesque 800 (display), Public Sans 400–700 (body) | Google Fonts |

Radii 10–24px, touch targets ≥ 44px, every page works at phone width.

## Roles

Visitor · Member · Aspirant/Candidate team · Mobilizer · Volunteer (member flag) · Party staff: HQ admin, Elections board, Treasurer, Comms officer, County official (scoped to one county) · Polling clerk (voting day, one centre) · Agent/observer (view-only) · Vendor staff (no party data without a party-approved, time-limited grant).

## Journeys and screens

**Sign-in** — `SignIn` (phone+SMS code for members/campaigns; email+password+2FA for staff) → `SysCode` / `SysReset` → `SysChooser` ("Where to?", only roles the person holds).

**1 · Visitor → member** — `PartyHome` → `Join` (3 steps + M-Pesa fee, one-party declaration, consent) → `Members` (CRM verification queue: duplicate ID, other-party register, fee check) → `MemberAccount` (card, renewal, My branch, My tasks, Elections, My nomination, My data & privacy).
Public pages: `PartyHome`, `News`, `PubArticle` (news article), `Events`, `PubIssue` (issue/position template), `PubBranch` (county branch), `PubAbout` (about, leadership, party organs, documents), `Candidates` (directory), `Candidate` (profile), `PubResults` (primary results + receipt checker).

**2 · Member → nominee** — `FlowTimetable` (dates, fees per seat, requirements; two-person sign-off) → `FlowApply` (aspirant: seat, documents, fee, declaration) → `CrmNominations` (vetting queue + checklist) → primaries: `VoteControl` (control room; counts sealed until two keyholders close polls), `VoteBallot` (online ballot, SMS-code confirm, receipt code), `VoteUssd` (USSD menu), `VoteClerk` (polling-centre check-in; one vote per member across all channels) → `FlowResults` (tally per centre, declare, certificate) → `CrmAppeals` (panel conflict declarations, ruling updates the seat) → `Nominees` (one nominee per seat; IEBC submission locked until every seat is resolved) + `CrmPartyLists` (ranked lists for nominated seats; live checks for gender alternation and special-interest inclusion; NEC approval). Public outcome: `PubResults`.

**3 · Nominee → campaign** — `Plans` (seat-based subscription) → `WsSetup` (race from nomination, auto ward targets, team invites, sharing defaults all off) → `Workspace` (strategy, win number, party feed, sharing toggles) → `WsTargets` (turnout slider recalculates win number per ward; drill to polling centres) → `WsEvents` → `WsMobilizers` → `WsSupporters` (consent record per person; never shared with the party) → `WsMessages` (SMS to opted-in supporters or the team, by ward; no WhatsApp — its business platform bars political use) → `WsParty` (party feed + sharing toggles, live "what the party sees" preview, sharing history) → `WsAgents` (one agent per polling station, station result forms, parallel tally) → `WsSpending` (expenses with receipts, contributions, declaration export) → `Mobilizer` (phone app, offline).

**4 · Running the party** (hub — all from the CRM sidebar) — `PartyCRM` (overview), `Members`, `CrmBranches` (+ `FlowSubBranch`, `FlowOfficials`), `CrmEvents` (audience, SMS invites, door check-in, website visibility), `CrmAppeals`, `CrmNominations`, `Nominees`, `CrmComms` (opted-in only, approval before send), `CrmFinance` (M-Pesa reconciliation, disclosure flags), `Content` (homepage, news with approval, branding), `CrmUsers` (roles & scope, data-protection requests, retention) + `FlowInvite`.

**5 · Vendor → party** — `Vendor` (parties, onboarding wizard with required data processing agreement, invoices, support-access requests).

Also: `SysStates` (error and empty states), `Flow` (system map of everything above).

## Rules the build must enforce

1. **Configurable, never hard-coded:** fees, tie-breaks, appeal windows, nomination methods, who may nominate directly — each party sets these from its own constitution.
2. **Tenancy:** party data fully isolated per party; each candidate workspace sealed inside its party. Party roles can't open a candidate's supporters.
3. **Consent:** store wording + notice version + date + channel for every consent; opt-outs stay listed (never messaged, never exported).
4. **Data subject rights:** access, correction, deletion, withdraw consent — from the member's account and a CRM request queue with due dates.
5. **Two-person / evidence gates:** timetable publish, closing polls, officials changes (signed minutes), certificates (two signatories).
6. **Secret ballot:** record *that* someone voted, never *who they chose*; receipt codes verify inclusion only. One vote per member across online, USSD and paper.
7. **Audit log** on every decision: who, when, under which rule, with which document.
8. Staff accounts require 2-step sign-in; election-day roles expire automatically.

## Coverage

Every step in the five journeys now has a screen. Remaining work is detail, not new areas: tablet layouts, Kiswahili copy throughout, print styles for certificates and declarations, and notification templates (SMS and email wording).

## Suggested build order

1. Tenancy, auth, roles and audit log (foundation for everything).
2. Journey 1: public site, join, verification, member account.
3. Journey 4 basics: branches, events, comms, finance (M-Pesa), users & data.
4. Journey 2: timetable → application → vetting → results → appeals → nominees board. Start with in-person primaries (clerk check-in + tally); add online/USSD after an independent security review.
5. Journey 3: candidate workspace (reuse the existing campaign CRM: Django/DRF + React).
6. Vendor console and billing.

Open items before real use: ODPC registration, privacy notice, data processing agreements (vendor ↔ party ↔ candidates), legal review of electronic primaries against each party's rules.
