#!/usr/bin/env bash
# Build the dashboard for Vercel.
#
# Mirrors scripts/build_frontend.sh, with one deliberate difference: the static
# assets go to public/ (Vercel's static output directory) and NO index.html is
# produced. The page is rendered per request by api/render.js — an index.html in
# public/ would be served in preference to it and would freeze the dashboard at
# deploy time, which is the exact failure this architecture exists to avoid.
#
#   public/app.js    the client bundle that hydrates the page
#   public/gds.css   compiled GDS tokens + utilities
#   public/fonts/    Euclid Circular
#
# api/render.js additionally needs frontend/dist-ssr/entry-server.js, which is
# traced into the function bundle from its import.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"
PUBLIC_DIR="${ROOT_DIR}/public"

cd "$FRONTEND_DIR"

echo "==> Installing frontend dependencies"
npm ci --no-audit --no-fund

echo "==> Building SSR bundle"
npm run build:ssr

echo "==> Building client bundle"
mkdir -p "$PUBLIC_DIR"
REO_CLIENT_OUT_DIR="$PUBLIC_DIR" npm run build:client

echo "==> Compiling GDS stylesheet"
npx tailwindcss -i css/entry.css -o "${PUBLIC_DIR}/gds.css" --minify

echo "==> Copying Euclid Circular fonts"
rm -rf "${PUBLIC_DIR}/fonts"
cp -r node_modules/@graphprotocol/gds-css/styles/fonts "${PUBLIC_DIR}/fonts"

# Guard the invariant this script exists to protect.
if [ -f "${PUBLIC_DIR}/index.html" ]; then
  echo "ERROR: public/index.html exists; it would shadow the render function." >&2
  exit 1
fi

echo
echo "Built for Vercel:"
ls -la "$PUBLIC_DIR"
