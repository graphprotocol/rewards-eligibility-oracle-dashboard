#!/usr/bin/env bash
# Deploy the generated dashboard to a Cloudflare Pages PREVIEW URL so changes
# can be reviewed in a browser BEFORE merging to main / deploying to production.
#
# Each branch gets its own isolated preview URL, e.g.:
#   https://feat-gds-theme.reo-dashboard.pages.dev
# so you can compare GDS/theme work without touching the live dashboard.
#
# The dashboard output is fully static (index.html + gds.css + fonts/), so this
# deploys the pre-built output/ directory directly. Cloudflare does NOT run
# generate_dashboard.py at build time (that needs GRAPH_API_KEY / RPC secrets
# we don't want in CF), so the preview shows a data SNAPSHOT. To refresh it:
#
#     bash scripts/build_gds_tokens.sh   # (re)build gds.css + fonts into output/
#     python3 generate_dashboard.py      # regenerate output/index.html
#     bash scripts/preview_deploy.sh     # deploy this branch's preview URL
#
# Auth (read from the gitignored .env so secrets never hit chat/shell):
#   CLOUDFLARE_API_TOKEN    = token with Accounts > Cloudflare Pages > Edit
#   CLOUDFLARE_ACCOUNT_ID   = the CF account to deploy into
# (Falls back to `wrangler login` OAuth if the token is unset.)
#
# Requires Node.js; npx fetches wrangler on first use.
set -euo pipefail

PROJECT="${REO_PAGES_PROJECT:-reo-dashboard}"
BRANCH="${REO_PAGES_BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo preview)}"
OUT_DIR="${REO_OUTPUT_DIR:-output}"
BRANCH_SLUG="${BRANCH//\//-}"   # CF Pages branch alias uses dashes

if [ ! -f "${OUT_DIR}/index.html" ]; then
  echo "Error: ${OUT_DIR}/index.html not found. Run generate_dashboard.py first." >&2
  exit 1
fi

# Pick up CF creds from the gitignored .env if not already in the environment.
if [ -f .env ]; then
  [ -z "${CLOUDFLARE_API_TOKEN:-}" ] && CLOUDFLARE_API_TOKEN="$(grep -E '^CLOUDFLARE_API_TOKEN=' .env | tail -1 | cut -d= -f2-)"
  [ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ] && CLOUDFLARE_ACCOUNT_ID="$(grep -E '^CLOUDFLARE_ACCOUNT_ID=' .env | tail -1 | cut -d= -f2-)"
fi
export CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID
export CI=true   # non-interactive: never block on a prompt

# Ensure the Pages project exists (idempotent: ignore "already exists").
echo "Ensuring Pages project '${PROJECT}' exists..."
npx --yes wrangler pages project create "${PROJECT}" --production-branch main \
  >/dev/null 2>&1 || true

echo "Deploying ${OUT_DIR}/ to Cloudflare Pages (preview)"
echo "  project:     ${PROJECT}"
echo "  account:     ${CLOUDFLARE_ACCOUNT_ID:-(unset)}"
echo "  branch:      ${BRANCH}"
echo "  preview URL: https://${BRANCH_SLUG}.${PROJECT}.pages.dev"
echo ""

exec npx --yes wrangler pages deploy "${OUT_DIR}" \
  --project-name="${PROJECT}" --branch="${BRANCH}" --commit-dirty=true
