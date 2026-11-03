# Applying the UI kit to super-duper-crm

This folder (`ui-kit/`) is the **reference styling setup**. It is not a second app to ship. The working app stays `frontend/` (React + Vite, JavaScript) and `backend/` (FastAPI). The agent brings the kit into `frontend/` and moves screens over as it works through the tickets in `docs/Implementation_Plan.md`, then removes the old `frontend/src/index.css`.

Design reference:
- `docs/party-platform-design/party-platform-design/DESIGN_HANDOFF.md`
- mockups in `.../screens/*.dc.html`

Read `ui-kit/SETUP.md` for the rules and the size spec.

## Where the design and the plan differ — the plan wins

The mockups were drawn for a broader multi-party product. `docs/Implementation_Plan.md` is the scope for this repo:

| Mockups show | This repo does (per the plan) |
|---|---|
| Vendor console, many parties, subdomains | One installation = one party. Branding comes from the `PartySettings` singleton. No vendor console. |
| SMS sending, M-Pesa reconciliation, maps, USSD/online primaries, election-day agents | Deferred. Don't build those screens. Use their layout only where a v1 screen needs a similar pattern. |
| Roles such as Treasurer, Elections board, County official | v1 roles: Party Super Admin, Membership Officer, Nominations Officer, Finance Officer, Aspirant, Campaign Manager, Mobilizer. Map the screen labels to these. |
| Full website CMS | Fixed public pages with basic editable content (Release 4). |

Use the mockups for **look and layout**. Use the plan for **what exists**.

## Decision to make first: old iPhones (iOS 15)

`frontend/vite.config.js` targets `safari15` on purpose, to support an iPhone 7 on iOS 15. **Tailwind CSS v4 officially needs Safari 16.4+.** On iOS 15 some utilities degrade: colour opacity such as `bg-white/80` (color-mix), some shadow/ring defaults (`@property`), gradients. Plain colours, spacing and layout still work.

Pick one before the first styling ticket:

1. **Tailwind v3.4 (recommended if iOS 15 must stay supported).** Port `src/styles/globals.css` to a `tailwind.config.js`:
   - put the same token names under `theme.extend`
   - keep the CSS variables in `:root`
   - replace `@theme inline` with the config
   - replace `color-mix` opacities with explicit rgba tokens

   Component class names stay the same. Verify on iOS 15 (BrowserStack or a real device).
2. **Tailwind v4 and drop iOS 15.** Use the kit as-is, and change `cssTarget` to `safari16.4`. Record the decision in `system.md`.

Whichever is chosen, keep the kit's colour, radius, shadow and size values exactly.

## Integration steps (one ticket each, before Release 1 UI work)

1. **Add the styling foundation to `frontend/`:**
   - install the dependencies listed in `ui-kit/SETUP.md` §2
   - add the Tailwind Vite plugin (or v3 PostCSS)
   - add the `@` → `src` alias
   - copy `ui-kit/src/styles`, `lib`, `theme` and `components` into `frontend/src/`
   - import the fonts and `styles/globals.css` in `main.jsx`

   The kit files are `.tsx`/`.ts`. Vite builds them alongside `.jsx`. Either add a `tsconfig.json` (allowJs) or convert them to `.jsx` by removing the types. Decide once and stay consistent.
2. **Isolate the old CSS while migrating.** Until every screen is moved, Tailwind's base reset and `index.css` will fight. Scope the old styles by wrapping legacy pages in a `.legacy` root (prefix the `index.css` selectors), or load `index.css` only on routes not yet migrated. New and migrated screens use only kit components.
3. **Layouts first:**
   - `PublicLayout` (SiteHeader, SiteFooter) for public routes
   - `AppLayout` + `AppPage` (CrmTopBar, sidebar) for party staff and campaign routes

   The sidebar items follow the plan's v1 pages, not the mockup's full list.
4. **Branding:**
   - wire `ui-kit/backend/branding.py` into `backend/src/backend` as a router
   - make `get_party_settings` read `PartySettings`, with logo and colours from the Release 1 Party Settings ticket
   - validate the contrast rule
5. **Migrate screen by screen inside the plan's tickets.** When a ticket touches a screen:
   - build or rebuild it with kit components
   - compare it with its mockup at 1440px and 390px
   - delete the matching rules from `index.css`
6. **Remove `index.css`** when no route uses `.legacy` any more. Then run the full test suite and the route-guard inventory test.

## Which mockup for which plan ticket

| Plan item | Mockup file(s) |
|---|---|
| R0 routing / split pages | layout only: `AppLayout`, `AppPage` |
| R1 Party Settings (logo, colours) | `Content` (Branding tab) |
| R1 Join the Party form + volunteer section | `Join` |
| R1 member management, search, exports | `Members`, `CrmUsers` (data requests) |
| R1 volunteers | `Members` (patterns), volunteer flag in `MemberAccount` |
| R1 withdrawal | `MemberAccount` (My data & privacy) |
| R2 aspirant approval + create workspace | `CrmNominations`, `FlowApply`, `WsSetup` |
| R3 plans, payments, access | `Plans`, `CrmFinance` (patterns) |
| R4 public pages | `PartyHome`, `PubAbout`, `News`, `PubArticle`, `Events`, `PubIssue` (manifesto) |
| R4 portal sign-in | `SignIn`, `SysCode`, `SysChooser` |
| R4 party dashboard | `PartyCRM` |
| Existing campaign CRM restyle | `Workspace`, `WsTargets`, `WsEvents`, `WsMobilizers`, `WsSupporters`, `Mobilizer` |
| Error / empty states | `SysStates` |
