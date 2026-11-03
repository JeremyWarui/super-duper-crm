# SETUP — styling that matches the mockups

This kit is the styling foundation for the party platform: the public website, the party CRM and the candidate workspace. The aim is that every screen looks exactly like the Design canvas mockups. Copy the files into the React app as described below, then build screens only from these parts.

Stack: React 19 + TypeScript + Vite, Tailwind CSS v4, shadcn-style components (Radix primitives), React Router, FastAPI backend.

---

## 1. What's in the kit

```
src/styles/globals.css          ← ALL design tokens + base styles (light only, no dark mode)
src/lib/utils.ts                ← cn() with tailwind-merge taught our custom sizes
src/theme/branding.tsx          ← loads party colours from FastAPI and applies them
src/components/ui/
  button.tsx    card.tsx    input.tsx (Input, Textarea, NativeSelect, Field)
  badge.tsx     tabs.tsx (Tabs, FilterPills)    table.tsx
  popover.tsx (Popover, DropdownMenu)    typography.tsx (SectionHead, RailHead, Crumbs, StoryMeta)
src/components/layout/
  Logo.tsx  SiteHeader.tsx (SiteUtilityBar, SiteHeader)  SiteFooter.tsx  PublicLayout.tsx
  AppSidebar.tsx (crmNav, workspaceNav)  CrmTopBar.tsx  AppPage.tsx  AppLayout.tsx
src/routes/                     ← demos: HomePage, MembersPage, KitPage (/kit)
backend/branding.py             ← FastAPI: GET /api/branding
components.json                 ← shadcn CLI config pointing at our paths
```

## 2. Install into an existing React + Vite app

```bash
npm install tailwindcss @tailwindcss/vite class-variance-authority clsx tailwind-merge \
  lucide-react @radix-ui/react-slot @radix-ui/react-tabs @radix-ui/react-popover \
  @radix-ui/react-dropdown-menu react-router-dom \
  @fontsource-variable/public-sans @fontsource-variable/bricolage-grotesque
npm install -D @types/node
```

1. Copy `src/styles`, `src/lib`, `src/theme`, `src/components` and `components.json` into the app.
2. `vite.config.ts`: add the `tailwindcss()` plugin, the `@` → `./src` alias, and the `/api` proxy to FastAPI (see this kit's `vite.config.ts`).
3. `tsconfig.app.json`: add `"paths": { "@/*": ["./src/*"] }`.
4. `src/main.tsx`: import the two `@fontsource-variable/*` packages, then `@/styles/globals.css`. Wrap the app in `<BrandingProvider>`.
5. Delete Vite's starter `index.css` and `App.css`. Nothing else may set global styles.
6. `index.html`: keep `<meta name="color-scheme" content="light">`.
7. Backend: include `backend/branding.py`'s router in the FastAPI app, and replace `get_party_settings` with a read of `PartySettings`.

## 3. Rules for whoever builds screens (human or agent)

1. **Light theme only.** Never add a `.dark` block, `dark:` classes, or a theme toggle. If a shadcn component you add later contains `dark:` classes, delete them.
2. **No raw colours in pages.** Use token classes (`bg-primary`, `text-muted-foreground`, `bg-stone`, `border-line`…). Hex values live only in `globals.css`. The one exception is a mockup colour used in a single place, which may go inline with a comment.
3. **Party colours come only from `--party-*`.** Never write `#0B5D3B` in a component, because each party re-brands it.
4. **Use the layouts.**
   - Website pages render inside `PublicLayout`.
   - CRM screens render inside `AppLayout kind="crm"`, and workspace screens inside `AppLayout kind="workspace"`.
   - Every app screen starts with `<AppPage crumb title context actions>`.
5. **Adding more shadcn components** (`npx shadcn@latest add dialog`, etc.) is fine. Afterwards, restyle them to the tokens:
   - remove any `dark:` classes
   - make controls at least `h-11`
   - use `rounded-lg` for fields and `rounded-[18px]` + `shadow-pop` for floating panels
   - check the result against the mockups
   - **Never** let the CLI overwrite `button`, `card`, `input`, `badge`, `tabs` or `table`. Answer "no" if it asks.
6. **Touch targets are at least 44px** (`h-11`) for buttons, inputs and nav items. Inputs use 16px text so phones don't zoom in.
7. **Placeholders stay in `[brackets]`** until real data is wired up. Never invent numbers.
8. **Accessibility:**
   - Every input sits in a `<Field label>`.
   - Icon-only buttons have an `aria-label`.
   - Focus rings are never removed.
   - Reduced motion is respected (`globals.css` handles this).

## 4. Shadcn vs. the mockups — what was changed and why

| shadcn default | Mockups | Where it's fixed |
|---|---|---|
| Neutral grey palette, `.dark` theme | Party green / gold / ink, warm neutrals, light only | `globals.css` `:root`, dark removed |
| One `--radius` (≈10px) for everything | 6 / 10 / 12 / 16 / 18 / 20 / 24 / 28 px by element | `@theme` radius scale + component variants |
| Buttons 36px, 6–8px corners | 44px (52px hero); pills on website, 12px corners in apps | `button.tsx` `size`, `shape` |
| Card: border + small shadow, 12px | Website: hairline + soft 2-layer shadow, 20px. CRM: 1px #E9E9E5 border, 16px | `card.tsx` `elevated` / `outline` / `tile` / `tinted` / `ink` / `panel` |
| Input 36px, 1px border | 50px website, 44px apps, 1.5px border, 12px corners | `input.tsx` `size` |
| Tabs: grey bar | Green pill inside a white capsule; newspaper underline | `tabs.tsx` `look` |
| No header / sidebar look | Frosted header with pill nav; dark-ink CRM sidebar; white workspace sidebar | `layout/*` |
| Inter / system fonts | Bricolage Grotesque 800 + Public Sans | fontsource + `--font-display/sans` |

## 5. Size spec — heights, widths and gaps (from the mockups)

Use these exactly. Tailwind classes are given where a token exists.

### Page frame
| Thing | Value | Class |
|---|---|---|
| Website content width | 1240px max, 24px side padding | `site-container` |
| Single-task flows | 1100–1200px max | `max-w-form` / `max-w-[1200px]` |
| CRM sidebar | 240px (desktop); 280px drawer on phones | `md:w-sidebar` |
| CRM content padding | 32px sides, 28px top, 40px bottom | `px-app pt-7 pb-10` |
| CRM top bar | 64px min height | in `CrmTopBar` |
| CRM page header | 18px vertical padding, 28px title | in `AppPage` |
| Website band padding | 80px top/bottom (72px on dark/green bands) | `py-20` / `py-[72px]` |
| Gap between band header and content | 28–32px | `gap-7` / `gap-8` |

### Header & footer
| Thing | Value |
|---|---|
| Utility bar | 13px text, 8px vertical padding, ink |
| Header | 14px vertical padding; logo tile 44×44, 12px corners; name 22px Bricolage 800 |
| Nav item | 15px semibold, 9×14px padding, pill; active = green tint + green text |
| Footer | 56px top padding; columns min 180px; legal row 13px |
| Newsletter band | 44px vertical padding; input 50px, min 260px wide |

### Controls
| Thing | Height | Corners | Text |
|---|---|---|---|
| Button md (default) | 44px | pill (site) / 12px (apps) | 15px bold |
| Button lg (hero) | 52px | pill | 17px bold, 28px side padding |
| Button sm | 40px | pill | 14px bold |
| Input / select (website) | 50px | 12px | 16px |
| Input / select (apps) | 44px | 12px | 16px |
| Segmented tabs | 40px buttons inside 3px capsule padding | pill | 14px bold |
| Status pill | ~22px | pill | 12px bold, 3×10px padding |
| Category label | ~22px | 6px | 12px extra-bold, uppercase, 0.1em tracking |
| Sidebar item | 44px (11px padding) | 10px | 15px semibold |

### Cards and media
| Thing | Corners | Padding | Notes |
|---|---|---|---|
| Website card (`elevated`) | 20px | 24px | hairline + `shadow-card`; `lift` on hover |
| Join / CTA panel (`panel`) | 24px | 32px | gold, green or white |
| CRM card (`outline`) | 16px | 24px | 1px #E9E9E5 |
| KPI tile (`tile`) | 16px | 20px | label 14px, number 28px Bricolage |
| Inner panel (`tinted`) | 12px | 16px | #F7F7F5 |
| Hero branch card | 22px | 24px | 360px wide, `shadow-hero-card` |
| Feature photo | 18–20px | — | `aspect-video` (16:9) |
| Story thumbnail | 12px | — | 104×76 (list), 112×112 (news stack), 16:10 (grid) |
| Candidate portrait | top of card | — | 1:1 |

### Grids (how cards line up)
| Grid | Rule |
|---|---|
| Agenda tiles | `grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4` |
| Candidates | `minmax(220px,1fr)`, `gap-5` |
| Events (home) | `minmax(260px,1fr)`, `gap-4` |
| Join panels | `minmax(280px,1fr)`, `gap-5` |
| KPI tiles | `minmax(180px,1fr)`, `gap-4` |
| Footer columns | `minmax(180px,1fr)`, `gap-7` |
| Main + side column | flex: main `flex-[3_1_520px]` (or `999 1 560px`), side `flex-[2_1_320px]` (or `1 1 300px`), `gap-6`–`gap-10` |

## 6. Making cards and components the same height and width

Yes, all of this is ordinary CSS and works with these components:

- **Equal heights in a row:** grid rows stretch their items by default, so cards in the same row share the tallest height. To pin a button to the bottom of every card, give the card `flex flex-col` (built in) and the button `mt-auto`:
  ```tsx
  <Card className="h-full"><CardTitle>…</CardTitle><p>…</p><Button className="mt-auto self-start">Register</Button></Card>
  ```
- **Equal widths:** `grid-cols-[repeat(auto-fit,minmax(Npx,1fr))]` gives equal columns that wrap on phones. For an exact count, use `grid-cols-3` (`md:grid-cols-3` etc.).
- **Fixed sizes from the mockup:** use arbitrary values, e.g. `w-[360px]`, `h-[76px]`, `min-h-[560px]`, or tokens such as `w-sidebar`.
- **Same image shape everywhere:** `aspect-video`, `aspect-[16/10]` or `aspect-square` on the placeholder or `<img>`, plus `object-cover` on real photos.
- **Long text doesn't break rows:** `min-w-0` on flex children and `line-clamp-2` on card titles keep cards the same height when one headline is long.
- **Phones:** every grid above collapses to one column by itself. Side columns drop under the main column. No horizontal scrolling, except data tables, which scroll inside their card (`Table minWidth`).

## 7. Per-party branding

`GET /api/branding` (see `backend/branding.py`) reads the singleton `PartySettings` record and returns the name, slogan, registration number, hotline, logo and four colours. `BrandingProvider` sets `--party-primary`, `--party-primary-hover`, `--party-primary-tint` and `--party-accent` on `<html>`, and everything follows. The CRM "Branding" screen must reject colours that fail 4.5:1 contrast, so a party can't make its own buttons unreadable.

## 8. Done check before shipping a screen

- [ ] Compared side-by-side with its mockup at 1440px and at 390px.
- [ ] No `dark:` classes, no raw party hex, no new global CSS.
- [ ] All controls at least 44px; every input labelled.
- [ ] No horizontal scroll at 390px.
- [ ] Placeholders still in `[brackets]` where data isn't wired.
