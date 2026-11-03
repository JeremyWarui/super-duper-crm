# Party Platform — UI kit (React + Tailwind v4 + shadcn-style components)

Styling setup that reproduces the Design canvas mockups exactly: colours, corner radii, shadows, fonts, sizes, headers, footer, CRM shell. Light theme only.

**Read `SETUP.md` first.** It has the install steps, the rules the coding agent must follow, and the size spec (heights/widths) taken from the mockups.

```bash
npm install
npm run dev          # http://localhost:5173  — /  (homepage demo), /kit (all parts), /crm/members (CRM demo)
npm run build
```
Backend piece: `backend/branding.py` (FastAPI router for per-party colours).
