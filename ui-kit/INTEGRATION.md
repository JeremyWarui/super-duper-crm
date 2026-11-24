# The UI kit in super-duper-crm

This folder (`ui-kit/`) is the **reference styling setup**. It is not a second app to ship.
The working app is `frontend/` (React + Vite) and `backend/` (FastAPI). The kit's styles,
`lib`, `theme` and components live in `frontend/src/`, and every screen is built from them.
Where the kit and `frontend/src/` differ, `frontend/src/` is right.

Design reference: the Design canvas mockups in
`docs/party-platform-design/party-platform-design/screens/*.dc.html`, with
`DESIGN_HANDOFF.md` beside them.

## Mockups and what the app does

The mockups were drawn for a broader product than this repo builds. Use them for **look and
layout**; use `docs/SYSTEM.md` for **what exists**.

| Mockups show | This repo does |
|---|---|
| A vendor console, many organisations, subdomains | One installation runs one candidate's campaign for one seat. Branding comes from the site settings. No vendor console. |
| Screens for features this product leaves out (primaries voting, USSD, maps, election-day work) | Not built. Their layout is reused only where a built screen needs a similar pattern. |
| Roles such as Treasurer or County official | The workspace roles: Candidate, Campaign Manager, Coordinator, Comms officer, Mobilizer, Agent, plus the superuser's console. |

## How the kit is wired into `frontend/`

- **Styles.** `frontend/src/styles/globals.css` holds every token, imported once with the
  fonts in `main.jsx`. Nothing else sets global styles.
- **Browsers.** Tailwind CSS v4 needs Safari 16.4 or later; `frontend/vite.config.js` builds
  for `safari16.4`. iOS 15 is not supported.
- **Layouts.** `PublicLayout` (`SiteHeader`, `SiteFooter`) wraps the public website.
  `AppLayout` and `AppPage` (`CrmTopBar`, `AppSidebar`) wrap the campaign workspace;
  `ConsoleShell` wraps the console. The sidebar items are each role's pages, not the mockup's
  full list.
- **Branding.** `frontend/src/theme/branding.tsx` reads the site settings (`GET /api/site/`)
  and sets the `--brand-*` colours on the page. `backend/src/backend/services/branding.py`
  refuses colours that fail 4.5:1 contrast with the text set on them.
- **Kit names.** The kit's own colour variables and its sample `backend/branding.py` router
  use other names. In the app, use the `--brand-*` variables and the site settings.

## Which mockup for which screen

| Screen | Mockup file(s) |
|---|---|
| Campaign workspace shell and Overview | `Workspace`, `CrmTopBar` |
| Targets | `WsTargets` |
| Events | `WsEvents` |
| Mobilizers | `WsMobilizers` |
| Agents | `WsAgents` |
| Contacts | `WsSupporters` |
| Messages | `WsMessages` |
| Mobilizer's phone pages | `Mobilizer` |
| First-run setup | `WsSetup` (patterns) |
| Website settings and editor | `Content` |
| Public pages | `News`, `PubArticle`, `Events`, `PubIssue`, `PubAbout`, `Candidate` |
| Sign-in and password reset | `SignIn`, `SysReset` |
| Error and empty states | `SysStates` |

When a change touches a screen, build it with kit components and compare it with its mockup at
1440px and 390px.
