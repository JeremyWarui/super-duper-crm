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
npm test           # 129 tests, jsdom, no server needed
npm run build
npm run lint
```

## Signing in

Each role sees a different app, so `campaign-crm demo` seeds one account per role
against the same campaign. Sign out and back in to switch between them.

| Username | What they get |
|---|---|
| `aspirant` | Candidate: overview, ward performance, events, strategy. Read-only. |
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

## Known gaps

1. The dashboard works on the first campaign the API returns. A user with two
   campaigns has no way to pick between them.
2. `App.jsx` carries Tailwind-style class names (`flex`, `gap-3`) inherited from
   the prototype. Tailwind is not installed; the inline styles do the layout and
   those classes do nothing.
3. `Btn` and `Select` are declared inside `Onboarding`, so they are new component
   types on every render. `npm run lint` warns about it.
4. The shell widens above 1440px and scales below it, so dragging a window
   across that boundary is a visible step. Both sizes are right on their own;
   only the transition is abrupt.
