# MZIGO Party Platform: Revised Concrete Execution Plan

## Goal

Convert the existing campaign CRM into a self-hosted political-party platform without breaking current campaign features.

The first sellable version enables a party to:

1. Run a public website.
2. Register and manage party members.
3. Maintain a volunteer register.
4. Approve party members as aspirants.
5. Create CRM workspaces for approved aspirants.
6. Activate, suspend, and manually charge for aspirant CRM access.
7. View basic party-wide campaign totals.

## Foundation Decisions

- One installation serves one political party.
- The party owns its domain, hosting, database, external-service accounts, and backups.
- There is no multi-party SaaS logic.
- One `PartySettings` record configures the installation.
- Party members, volunteers, and campaign supporters are distinct concepts.
- An aspirant must be an approved party member.
- A volunteer must be an approved party member.
- Volunteers have no login or campaign access by default.
- The existing campaign CRM remains intact.
- Aspirant billing starts as a manual staff workflow.
- Payment gateways, maps, advanced CMS, and regional coordination roles are deferred.

## Version 1 Roles

| Role | Access |
|---|---|
| Party Super Admin | All platform, membership, volunteer, aspirant, subscription, and report functions |
| Membership Officer | Party-member and volunteer records |
| Nominations Officer | Aspirant approval, suspension, and campaign creation |
| Finance Officer | CRM plans, payments, subscriptions, and access |
| Aspirant | Their own campaign CRM only |
| Campaign Manager | Existing campaign-management access |
| Mobilizer | Existing limited field access |
| Party Member | No portal access by default |
| Volunteer | No portal access by default |

## Release 0: Prepare the Existing CRM

### Objective

Make the current system safe to extend.

### Tasks

- Document and correct differences between `system.md` and the actual code.
- Resolve the duplicate role source: `users.role` and `campaign_members.role`.
- Add a database-backed rule preventing campaign-role mismatch.
- Add audit-log infrastructure.
- Audit existing sensitive actions.
- Store supporter consent wording and consent channel.
- Add SPA fallback for direct links and page refreshes.
- Add routing and split the large campaign frontend into smaller pages.
- Add a route-guard inventory test.
- Keep all existing campaign permissions and workflows unchanged.

### Completion Gate

- Existing tests pass.
- Composite foreign-key migration is proven on Postgres.
- Campaign isolation and role rules remain intact.
- New frontend addresses work after a browser refresh.
- No membership, volunteer, aspirant, or subscription feature has been built yet.

## Release 1: Party Identity, Membership, and Volunteers

### Objective

Create the party’s public identity, member register, and basic volunteer register.

### Tasks

#### Party Settings

Add one singleton `PartySettings` record:

- party name and short name;
- logo and colours;
- contact information;
- public description;
- social links;
- manifesto text or document link.

#### Party Roles

Add party-level roles:

- Membership Officer;
- Nominations Officer;
- Finance Officer.

Use the existing `is_superuser` as Party Super Admin. At handover, the party must own at least two Super Admin accounts.

#### Party Members

Add `PartyMember`:

- full name;
- phone;
- optional email;
- ward;
- membership status;
- application date;
- consent wording;
- consent date and time;
- consent channel;
- withdrawal code.

Membership status:

- pending;
- approved;
- rejected;
- suspended;
- withdrawn.

Build:

- public “Join the Party” form;
- party-member withdrawal process;
- Membership Officer member-management page;
- search, filters, status changes, and audited exports.

#### Volunteers

Add an optional one-to-one `VolunteerProfile` linked to an approved party member.

```text
PartyMember
  └── VolunteerProfile, optional
```

Volunteer fields:

- status: `interested`, `active`, `inactive`, `withdrawn`;
- interests: mobilisation, events, communications, social media, fundraising, administration, polling-day support;
- availability notes;
- preferred contact method;
- volunteer-contact consent wording;
- volunteer-contact consent timestamp.

Add an optional volunteer section to the public membership form:

- “I would like to volunteer for the party.”
- volunteer interests;
- preferred contact method;
- separate consent to receive volunteer opportunities.

Membership Officers can:

- view volunteers;
- search by location, interest, and status;
- activate or deactivate a volunteer;
- update availability notes;
- export volunteer records under the same audit controls as member exports.

### Completion Gate

- Citizens can apply for party membership.
- Membership Officers can manage membership applications.
- Approved members can express interest in volunteering.
- Volunteers can withdraw volunteer-contact consent without withdrawing party membership.
- Volunteers have no portal, campaign, finance, supporter, or mobilizer access by default.
- Campaign supporters remain unaffected.

## Release 2: Aspirants and Campaign Creation

### Objective

Allow the party to approve party members as aspirants and create their CRM workspaces.

### Tasks

- Add `Aspirant` linked to an approved `PartyMember`.
- Record seat sought, electoral area, nomination status, decision date, and reason.
- Add statuses: draft, submitted, approved, rejected, withdrawn, suspended.
- Build the Nominations Officer workflow:
  - find approved members;
  - create aspirant record;
  - approve or reject nomination;
  - create campaign workspace.
- Reuse the existing campaign-creation flow.
- Preserve the one-login, one-campaign rule.
- Allow a party officer also to be an aspirant, but prohibit them from acting on their own membership, nomination, subscription, or finance record.
- Change campaign deletion behaviour before linking aspirant logins to party-member records.

### Completion Gate

- Only approved party members can become aspirants.
- Only Nominations Officers or Party Super Admins can approve an aspirant.
- An aspirant can access only their own campaign CRM.
- Existing campaign-manager and mobilizer restrictions remain enforced.

## Release 3: Manual CRM Subscription Management

### Objective

Allow the party to charge aspirants and control access to campaign CRM workspaces.

### Tasks

- Add CRM plans: name, price, duration, description, active status.
- Add campaign subscriptions: plan, status, dates, payment reference, amount, and notes.
- Add statuses:
  - pending payment;
  - active;
  - grace period;
  - read-only;
  - locked;
  - cancelled.
- Build a Finance Officer page to:
  - create plans;
  - assign a plan;
  - record a manual payment;
  - activate or extend access;
  - suspend access.
- Enforce access centrally:
  - active and grace period: normal access;
  - read-only: data visible but not editable;
  - locked: campaign workspace unavailable except payment status.
- Add basic revenue and expiring-subscription reports.

### Completion Gate

- Party staff can activate or suspend CRM access without developer help.
- An expired campaign cannot edit campaign data.
- Finance data is visible only to Finance Officers and Party Super Admins.
- No payment gateway is required yet.

## Release 4: Public Website and Basic Party Dashboard

### Objective

Deliver the first complete, sellable party platform.

### Tasks

Build fixed public pages:

- home;
- about;
- leadership;
- manifesto;
- news;
- events;
- join the party;
- portal sign-in.

Allow Party Super Admins to edit basic public content.

Build a party dashboard showing:

- approved members;
- pending applications;
- active volunteers;
- volunteers by location and interest;
- approved aspirants;
- active campaigns;
- active CRM subscriptions;
- upcoming campaign events;
- campaign totals by county and seat;
- recorded CRM revenue.

Use tables and filters before maps:

- county;
- constituency;
- ward;
- electoral seat;
- aspirant;
- date range.

### Completion Gate

- The party has a branded public website.
- Party staff can manage members and volunteers.
- The party can approve aspirants and activate their CRM workspaces.
- Party leaders can view useful high-level totals.
- The party can operate the installed platform independently.

## Deferred Until After Version 1

- Volunteer assignment to campaigns or events
- Volunteer task management and attendance
- Converting volunteers into mobilizers
- Payment-gateway and mobile-money integration
- SMS credits and sending
- Full content-management system
- County, constituency, and ward coordinator roles
- Advanced maps
- Offline field capture
- Election-day polling-station tools
- Automated invoices and receipts
- Multi-party SaaS deployment

## Agent Workflow

- Claude Opus 5.5 plans, reviews, integrates, and approves ticket sequencing.
- Claude Sonnet 5.5 implements small, isolated tickets with tests.
- Do not run migration tickets in parallel.
- Every ticket must define affected files, permission rules, migration needs, tests, and acceptance criteria.
- Use practical DRY; reuse stable shared code, but avoid premature abstraction.
- Use no comments unless needed for non-obvious security, privacy, consent, or business rules.
- Update `system.md` after each accepted release.