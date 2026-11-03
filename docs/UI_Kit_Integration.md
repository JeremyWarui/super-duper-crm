# UI kit integration

Brings `ui-kit/` into `frontend/` as `ui-kit/INTEGRATION.md` describes, then
moves screens over ticket by ticket. Visual reference:
`docs/party-platform-design/party-platform-design/DESIGN_HANDOFF.md` and its
`screens/*.dc.html`. Where a mockup shows more than `docs/Implementation_Plan.md`
(and the Release 5 design, `docs/Volunteers_Design.md`), the plan wins.

Decisions (Jeremy, 3 November 2026):

- Tailwind CSS v4, as the kit ships it. iOS 15 (iPhone 7) is no longer
  supported; `build.cssTarget` moves to `safari16.4`.
- Kit files stay `.tsx`/`.ts`, copied verbatim so a kit update drops in.
  `tsconfig.json` allows JavaScript; the app's own pages stay `.jsx`.
- `ui-kit/` at the repository root is the reference; its screenshots are not
  committed.

Every screen a ticket touches is rebuilt with kit components, compared with its
mockup at 1440px and 390px (screenshots kept outside the repo), and its old
`index.css` rules are removed. Existing tests keep passing. Each ticket gets one
cold critic judged on its own text.

## Tickets

**UI-1 Styling foundation**
- Files: `frontend/package.json` (the kit's dependencies at the kit's versions), `vite.config.js` (`@tailwindcss/vite`, the `@` alias for build and tests, the `/api` dev proxy, `cssTarget` `safari16.4`), `tsconfig.json` (allowJs, `@/*` paths, react-jsx), `components.json`, `src/styles/`, `src/lib/`, `src/theme/`, `src/components/ui/`, `src/components/layout/` (verbatim from the kit), `src/main.jsx` (fonts, `globals.css`, `BrandingProvider`), `index.html` (`color-scheme` light, no Google Fonts), `tests/styles.test.js`, `docs/SYSTEM.md` (the iOS decision).
- Permissions: none change. Migration: none.
- Tests: the build passes; a kit `Button` renders with the primary token class; every existing test passes.
- Acceptance: the kit's components import with `@/`; no screen changes yet beyond fonts.

**UI-2 Isolate the old stylesheet**
- Files: `src/index.css` (every selector scoped under `.legacy`; `:root`, `html` and `body` rules move onto `.legacy`), the components that render pages not yet moved (wrapped in a `.legacy` root), `tests/styles.test.js` (reads the scoped selectors).
- Permissions: none. Migration: none.
- Tests: every existing test passes; the stylesheet test still finds every class the components use.
- Acceptance: legacy pages look as before at 1440px and 390px; a kit component outside `.legacy` takes no style from `index.css`.

**UI-3 Layouts**
- Files: `components/PublicLayout.jsx` replaced by the kit's `PublicLayout` (`SiteHeader`, `SiteFooter`) for public routes; party console and campaign shells (`pages/party/Portal.jsx`, `App.jsx` `PortalLayout`) on the kit's `AppLayout` and `AppPage` with `CrmTopBar` and the sidebar. Sidebar items follow the pages that exist (party console by role; campaign pages by role), not the mockup's full list. Pages inside stay in `.legacy` until their own ticket.
- Permissions: navigation shows only what each role may open today; no route guard changes.
- Migration: none.
- Tests: each role sees exactly its sidebar items; the public header marks the current page; sign-in and sign-out still work.
- Acceptance: headers, sidebars and footers match `SiteHeader`, `SiteFooter`, `CrmTopBar` and the CRM shell at 1440px and 390px.

**UI-4 Branding from PartySettings**
- Files: `backend/src/backend/api/routers/branding.py` (`GET /api/branding` from `PartySettings`: name, short name (up to 3 letters), slogan, registration number, hotline from the contact phone, logo, primary, primary hover and tint derived from primary, accent from the secondary colour), `models/party.py` and a revision `party_branding` (`slogan`, `registration_number`), `schemas/party.py` (settings update refuses a primary below 4.5:1 against white text and an accent below 4.5:1 against ink #13201A), the website editor's branding fields, `PartyBrand.jsx` removed in favour of the kit's `Logo`, tests.
- Permissions: `GET /api/branding` is public; settings stay superuser-only.
- Migration: one revision, after `member_logins`.
- Tests: the endpoint answers from the settings; a low-contrast colour is refused; the frontend applies `--party-primary` from the answer.
- Acceptance: changing the party's colours and logo in the editor re-brands the site, console and CRM.

Then the screens move in the plan's order, inside the Release 5 tickets that touch them (`docs/Volunteers_Design.md` section 3 and section 8), using the mapping in `ui-kit/INTEGRATION.md`: party settings (`Content`), join (`Join`), members and volunteers (`Members`, `CrmUsers`), withdrawal (`MemberAccount`), aspirants (`CrmNominations`), plans and payments (`Plans`, `CrmFinance`), public pages (`PartyHome`, `PubAbout`, `News`, `PubArticle`, `Events`, `PubIssue`), sign-in (`SignIn`, `SysCode`, `SysChooser`), the party dashboard (`PartyCRM`), the campaign CRM (`Workspace`, `Ws*`, `Mobilizer`), and error and empty states (`SysStates`). When no route uses `.legacy`, `index.css` is deleted and the full suites and the route-guard inventory run.
