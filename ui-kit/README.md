# UI kit (React + Tailwind v4 + shadcn-style components)

The styling setup the app's screens are built from: colours, corner radii, shadows, fonts,
sizes, the website header and footer, and the app shell. Light theme only.

**Read `SETUP.md` first.** It has the rules for building screens and the size spec (heights and
widths) taken from the mockups. `INTEGRATION.md` says how the kit maps onto `frontend/`.

```bash
npm install
npm run dev          # http://localhost:5173: / (homepage demo), /kit (all parts), /crm/members (table demo)
npm run build
```

`backend/branding.py` is a sample FastAPI router. The app itself reads its branding from the
site settings (`GET /api/site/`).
