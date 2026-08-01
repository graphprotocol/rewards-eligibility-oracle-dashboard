#!/usr/bin/env bash
# Build the dashboard frontend for local development.
#
# Mirrors the Dockerfile `frontend-build` stage so a developer without Docker can
# produce everything generate_dashboard.py needs to render:
#
#   frontend/dist-ssr/entry-server.js  the self-contained SSR bundle
#   output/gds.css                     compiled GDS tokens + utilities
#   output/fonts/                      Euclid Circular
#
#   Usage:  bash scripts/build_frontend.sh
#   Then:   python3 generate_dashboard.py     # fetches data, writes data.json, renders
#
# Requires: Node.js >= 20. Unlike the old GDS-only script, dependencies are
# installed into frontend/node_modules (gitignored) rather than a temp dir,
# because the SSR build needs them and rebuilds are frequent during development.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"
OUT_DIR="${ROOT_DIR}/output"

cd "$FRONTEND_DIR"

echo "==> Installing frontend dependencies"
npm install --no-audit --no-fund

echo "==> Building SSR bundle"
npm run build:ssr

echo "==> Compiling GDS stylesheet"
mkdir -p "$OUT_DIR"
npx tailwindcss -i css/entry.css -o "${OUT_DIR}/gds.css" --minify

echo "==> Copying Euclid Circular fonts"
rm -rf "${OUT_DIR}/fonts"
cp -r node_modules/@graphprotocol/gds-css/styles/fonts "${OUT_DIR}/fonts"

echo
echo "Frontend built:"
echo "  ${FRONTEND_DIR}/dist-ssr/entry-server.js"
echo "  ${OUT_DIR}/gds.css"
echo "  ${OUT_DIR}/fonts/"
echo
echo "Next: python3 generate_dashboard.py"
