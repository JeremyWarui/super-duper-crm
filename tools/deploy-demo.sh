#!/usr/bin/env bash
# Create (if needed), configure and deploy one demo install as a Vercel project.
# Usage, from the repository root: tools/deploy-demo.sh <project-name> <NEON_PARTY|NEON_ASPIRANT|NEON_BLANK>
# Reads the connection string from backend/.env and never prints it.
set -euo pipefail

project="$1"
key="$2"
vercel() { npx.cmd -y vercel@latest "$@"; }

url=$(grep "^$key=" backend/.env | cut -d= -f2- | tr -d '\r')
case "$url" in postgresql://*) ;; *) echo "No $key in backend/.env" >&2; exit 1 ;; esac

vercel project create "$project" >/dev/null 2>&1 || true
vercel link --yes --project "$project" >/dev/null 2>&1

add() { printf '%s' "$2" | vercel env add "$1" production --force >/dev/null 2>&1; }
add DATABASE_URL "$url"
add SECRET_KEY "$(python -c 'import secrets; print(secrets.token_urlsafe(48), end="")')"
add PARTY_INBOX_SECONDS 0
add RECONCILE_HOURS 0
add CORS_ALLOW_ORIGINS '[]'
add DEBUG false

site=$(vercel deploy --prod --yes 2>&1 | grep -o '"productionUrl": "[^"]*"' | cut -d'"' -f4)
add PUBLIC_URL "$site"
vercel deploy --prod --yes >/dev/null 2>&1
echo "$project: $site"
