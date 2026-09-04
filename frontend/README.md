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
npm test           # 77 tests, jsdom, no server needed
npm run build
npm run lint
```

## Signing in

Each role sees a different app, so `campaign-crm demo` seeds one account per role
against the same campaign. Sign out and back in to switch between them.

| Username | Password | What they get |
|---|---|---|
| `aspirant` | `demo-aspirant-2027` | Candidate: overview, ward performance, events, strategy. Read-only. |
| `manager` | `demo-manager-2027` | Campaign manager: the above plus targets, mobilizers and supporters, and every write. |
| `mobilizer` | `demo-mobilizer-2027` | Mobilizer: their own ward only - my events, register supporter, my supporters. |

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
| `onboarding.test.jsx` | The four steps, the cascading pickers, and the win number that comes back |
| `app.test.jsx` | The dashboard, what each role is shown, and the four forms |
| `gate.test.jsx` | Which of the three screens you land on |

## Known gaps

1. The dashboard works on the first campaign the API returns. A user with two
   campaigns has no way to pick between them.
2. `App.jsx` carries Tailwind-style class names (`flex`, `gap-3`) inherited from
   the prototype. Tailwind is not installed; the inline styles do the layout and
   those classes do nothing.
3. `Btn` and `Select` are declared inside `Onboarding`, so they are new component
   types on every render. `npm run lint` warns about it.
