# Campaign CRM - frontend

React 19 and Vite, talking to the FastAPI backend. Zustand holds who you are;
React Query holds everything else.

## Quick start

The backend must be running first (see `../backend/README.md`).

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

`VITE_API_URL` defaults to `http://localhost:8000/api`. Point it elsewhere in a
`.env`; see `.env.example`.

Checks:

```bash
npm test           # 86 tests, jsdom, no server needed
npm run build
npm run lint
```

## Signing in

Each role sees a different app, so `campaign-crm demo` seeds one account per role
against the same campaign. Sign out and back in to switch between them.

| Username | What they get |
|---|---|
| `aspirant` | Candidate: overview, ward performance, events, mobilizers, team, strategy. Adds or replaces the manager, adds and assigns mobilizers; everything else is read-only. |
| `manager` | Campaign manager: targets, mobilizers, team and supporters, and every write. |
| `mobilizer` | Mobilizer: their own ward only - my events, register supporter, my supporters. |

The passwords are generated per run and printed by `campaign-crm demo`. Pass
`--password <value>` to pin all three instead.

## By organisation type

`src/app/site.js` reads the installation's type from `GET /api/site/` once, and
`src/copy.js` holds every word that differs by type. `Gate.jsx` serves the
shared website pages in both, the party's pages in a party installation, and in
an aspirant installation the candidate homepage at `/`, `/volunteer` and
`/volunteer/withdraw/:code`; a path only the other type serves goes to `/`. In
an aspirant installation the Candidate, Manager and Comms get the workspace
**Website** and **Settings** pages; in the party workspace a coordinator gets
**Recruitment**, their link and QR code to the Join the Party form.

## Styling

Plain CSS, no framework. Everything lives in `src/index.css`:

- **Tokens** at the top of `:root`: the colours, type scale (12 to 48px), radii and
  shadows. Change them there to retheme every screen.
- **One typeface**, Inter, loaded in `index.html`. Figures use tabular numbers so
  columns line up.
- **Tones**: a badge, bar, note or result takes `tone-good`, `tone-warn`,
  `tone-bad` or `tone-neutral`; components never carry colours of their own.
- **Shared pieces**: `Panel` (the card), `Button` (`primary`, secondary, or
  `tone="danger"`) and the field components in `src/components/ui`. In `App.jsx`
  the table, chip, segmented control, badge and modal classes are reused by every
  page.

Inline `style` is used only for values computed at runtime, such as a progress
bar's width. `tests/styles.test.js` fails if a component uses a class the
stylesheet does not define.

## Layout

```
frontend/
├── index.html
├── vite.config.js         also holds the vitest settings
├── src/
│   ├── main.jsx           mounts the app
│   ├── Gate.jsx           which screen: sign in, console, no campaign, dashboard
│   ├── App.jsx            the dashboard, one page per nav item
│   ├── api/
│   │   ├── client.js      one place that talks to the API
│   │   └── hooks.js       a query per read, a mutation per write
│   ├── store/auth.js      the token and the role, kept in localStorage
│   └── components/        Login.jsx, Admin.jsx (the console)
└── tests/
```

## How it hangs together

`Gate.jsx` decides which screen you are on: no token means `Login`; a superuser
gets `Admin`; a login on no campaign is told so and can sign out; otherwise `App`.

`App.jsx` reads `user.role` and picks that role's nav. The same role rules are
enforced on the server, so hiding a button is a convenience, not the control.

Every read is a React Query hook keyed by campaign. Every write is a mutation
that invalidates the caches it changed - scheduling an event refreshes the event
list *and* the strategy, because the strategy is computed from events.

Numbers are never worked out in the browser. The win number, each unit's
progress and the strategy notes all arrive computed, so the screen cannot
disagree with the database.

## Tests

```bash
npm test
```

| File | What it covers |
|---|---|
| `client.test.js` | The token header, the error message the user ends up seeing, sign-out on a dead token |
| `auth.test.js` | Sign in, sign out, and staying signed in across a reload |
| `hooks.test.js` | Which query each hook sends, and what a write refreshes |
| `login.test.jsx` | The sign-in form, including the rejected password |
| `onboarding.test.jsx` | The console's new-campaign wizard: the cascading pickers, the unit preview, and the win number |
| `app.test.jsx` | The dashboard, what each role is shown, the four forms, and inviting |
| `gate.test.jsx` | Which screen you land on: sign-in, the console, not on a campaign, or the dashboard |
| `team.test.jsx` | The Team page: replacing the manager, and no password resets |
| `join.test.jsx` | Signing up from an event or the campaign link, sharing both links, and withdrawing |
| `contract.test.js` | The fixtures and the source still match `contracts/frontend-api.json` |

## Two things the prototype did not have

**Setup previews its units.** Before the campaign is created, the review step
lists what it will be worked on: every ward in the county or constituency, or
every registration centre in the ward, each with its register and a total. A
ward with no centres loaded says so there, rather than looking ready and coming
back with a win number of zero.

**Nobody sets a campaign up for themselves.** An aspirant copy's one workspace is
made at setup (`pages/setup/Setup.jsx`). On a party copy the console's **New
campaign** opens Aspirants, where a Nominations Officer makes an approved
aspirant's workspace; its logins are emailed invite links.

**A login on no campaign is told so.** An aspirant, manager or mobilizer whose
campaign list is empty sees "You are not on a campaign yet" and can sign out;
they are never shown setup.

**Mobilizers are added from inside a campaign.** The Mobilizers page adds them,
with a login or without one, for a manager and a candidate alike, each password
shown once. In an MCA race the page and its form speak of centres, and offer
only the centres with a target.

**The Team page runs the logins.** It lists everyone on the campaign. The
aspirant sees **Add manager**, or **Replace manager** once there is one, which
warns that the old manager loses their login. The new manager's password is
shown once, in a box a stray click on the backdrop does not close. Nobody on a
campaign resets a teammate's password; only the superuser does.

**A superuser gets the console, not a campaign.** `Gate.jsx` sends an account
with `is_superuser` to `Admin.jsx` instead of the campaign gate: every campaign
on the deployment with its team and its size, every login and where it reaches,
and the repairs that cannot be done from inside a campaign (reset a password,
disable a login, put somebody on a campaign or take them off, rename or delete a
campaign). A campaign with nobody on it is called out in red, because nobody can
see it until somebody is put on. The flag only decides what the browser draws;
every route it calls checks it again.

**The console makes logins.** The Logins tab creates a campaign manager or a
mobilizer, with the password shown once. A manager can be put on a campaign as
it is made, if the campaign has none yet, or left unplaced; a mobilizer must be
given a campaign and one of its wards (in an MCA race, one of its centres with a
target), or they sign in scoped to nothing. An aspirant is never made on their
own: they get their login with their workspace, from Aspirants or at setup.

Nothing destructive fires on one click: taking somebody off, disabling a login,
resetting a password and deleting a campaign each ask first, naming who or what
they are about. A reset
password is collected by the console itself rather than by the row that asked
for it, so switching tabs mid-request cannot lose the one copy that exists. The
operator's own row offers neither Disable nor Reset password, because both would
end their session before they could act on the result.

**Events can be invited.** Each event on the Events page has an Invite button.
The modal drafts a message from the event, counts the SMS parts it will be
billed at, filters by where people stand, and previews the recipients before
sending. It says plainly when nothing was sent, which is the case until there
is an Africa's Talking subscription.

## Field screens on a phone

Mobilizers and agents get a tab bar at the bottom of the screen below 768px (`pages/campaign/FieldTabs.tsx`). My events leads with the next event and a reached/attended counter (`AttendanceCard.jsx`).

Register supporter and the attendance counter keep what is typed in `localStorage` (`lib/draft.js`, keys `draft:<user>:<form>`) until it is sent. With no network the entry stays and Try again resends it. Signing out removes every draft; an expired session keeps them for the same person.

Kit tables take `stack`: below 640px each row becomes a card, with each cell labelled by its column heading, so nothing is wider than the screen.

### Known gaps

- If the server saves a supporter but the reply is lost, Try again posts again and the server refuses the duplicate phone.
- A request that hangs, instead of failing, shows "Saving…" until the page is reloaded.
- No full offline sync: drafts live on the one device only.

## The contract

`../contracts/frontend-api.json` lists every field this app reads and sends.
`contract.test.js` checks the fixtures and the source against it;
`backend/evals/test_frontend_contract.py` checks the API against the same file.
Renaming a field on one side fails on both until the other side is updated.
