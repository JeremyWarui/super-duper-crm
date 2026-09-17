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
npm test           # 267 tests, jsdom, no server needed
npm run build
npm run lint
```

## Signing in

Each role sees a different app, so `campaign-crm demo` seeds one account per role
against the same campaign. Sign out and back in to switch between them.

| Username | What they get |
|---|---|
| `aspirant` | Candidate: overview, ward performance, events, mobilizers, strategy. Adds and assigns mobilizers; everything else is read-only. |
| `manager` | Campaign manager: the above plus targets, mobilizers and supporters, and every write. |
| `mobilizer` | Mobilizer: their own ward only - my events, register supporter, my supporters. |

The passwords are generated per run and printed by `campaign-crm demo`. Pass
`--password <value>` to pin all three instead.

## Layout

```
frontend/
├── index.html
├── vite.config.js         also holds the vitest settings
├── src/
│   ├── main.jsx           the gate: sign in -> set up -> dashboard
│   ├── App.jsx            the dashboard, one page per nav item
│   ├── api/
│   │   ├── client.js      one place that talks to the API
│   │   └── hooks.js       a query per read, a mutation per write
│   ├── store/auth.js      the token and the role, kept in localStorage
│   └── components/        Login.jsx, Onboarding.jsx
└── tests/
```

## How it hangs together

`main.jsx` decides which of three screens you are on: no token means `Login`; a
token with no campaign means `Onboarding`; otherwise `App`.

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
| `onboarding.test.jsx` | The four steps, the cascading pickers, the unit preview, and the win number |
| `app.test.jsx` | The dashboard, what each role is shown, the four forms, and inviting |
| `gate.test.jsx` | Which of the three screens you land on |
| `contract.test.js` | The fixtures and the source still match `contracts/frontend-api.json` |

## Two things the prototype did not have

**Setup previews its units.** Before the campaign is created, the review step
lists what it will be worked on: every ward in the county or constituency, or
every registration centre in the ward, each with its register and a total. A
ward with no centres loaded says so there, rather than looking ready and coming
back with a win number of zero.

**Setup knows whose campaign it is.** A manager is asked first who they are
running for. Aspirants they already set up are offered in a picker, so a second
campaign for one of them reuses that login rather than colliding with the
username; otherwise they name a new one, with first and last name, username,
email and phone. Either way the campaign belongs to that aspirant, not to the
manager who typed it in, and the review screen says which of the two is about to
happen. A new aspirant never signs up: they get a login whose password is shown
once on the screen that follows. Nothing is emailed yet, so the address is only
kept on record. A candidate signing up gets the shorter flow and their own
campaign.

**Setup adds the mobilizers.** The screen that shows the win number adds
mobilizers, each with a generated password shown once. The Mobilizers page does
the same later, with a login or without one, for a manager and a candidate
alike. Nobody adds a campaign manager from inside a campaign.

**A superuser gets the console, not a campaign.** `main.jsx` sends an account
with `is_superuser` to `Admin.jsx` instead of the campaign gate: every campaign
on the deployment with its team and its size, every login and where it reaches,
and the repairs that cannot be done from inside a campaign (reset a password,
disable a login, put somebody on a campaign or take them off, rename or delete a
campaign). A campaign with nobody on it is called out in red, because nobody can
see it until somebody is put on. The flag only decides what the browser draws;
every route it calls checks it again.

**The console makes logins.** The Logins tab creates a campaign manager, an
aspirant or a mobilizer, with the password shown once. A manager can be put on a
campaign as it is made, or left unplaced; a mobilizer must be given a campaign
and one of its wards, or they sign in scoped to nothing. An aspirant is made on
their own: a campaign belongs to the one candidate it names, so theirs is set up
afterwards and becomes theirs then.

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

## The contract

`../contracts/frontend-api.json` lists every field this app reads and sends.
`contract.test.js` checks the fixtures and the source against it;
`backend/evals/test_frontend_contract.py` checks the API against the same file.
Renaming a field on one side fails on both until the other side is updated.
