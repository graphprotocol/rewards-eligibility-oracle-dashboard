#!/usr/bin/env bash
# Build The Graph Design System (GDS) stylesheet + fonts for local development.
#
# This mirrors the Dockerfile `gds-build` stage so a developer without Docker can
# produce the gds.css + fonts/ assets that generate_dashboard.py links. Tailwind v4
# only emits a light-dark() semantic token when a matching utility class is scanned;
# @source points at generate_dashboard.py so the class names listed in the kitchen-sink
# HTML comment force every token + theme class to compile into gds.css.
#
#   Usage:  bash scripts/build_gds_tokens.sh
#   Then:   python3 generate_dashboard.py
#
# Output:  ./output/gds.css and ./output/fonts/  (next to index.html)
# Requires: Node.js >= 18 (for npx). npm packages are installed in a throwaway temp
# directory and are never added to the repository.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$(mktemp -d)"
OUT_DIR="${ROOT_DIR}/output"
trap 'rm -rf "$BUILD_DIR"' EXIT

# Replicate the Docker layout: generate_dashboard.py at the build root so the
# @source '../generate_dashboard.py' path in entry.css resolves identically.
cp "${ROOT_DIR}/generate_dashboard.py" "${BUILD_DIR}/generate_dashboard.py"
cd "$BUILD_DIR"

npm install tailwindcss@^4 @tailwindcss/cli @graphprotocol/gds-css --no-audit --no-fund

mkdir -p src out
printf "@import 'tailwindcss';\n@import '@graphprotocol/gds-css';\n@source '../generate_dashboard.py';\n" > src/entry.css
npx @tailwindcss/cli -i src/entry.css -o out/gds.css
cp -r node_modules/@graphprotocol/gds-css/styles/fonts out/fonts

mkdir -p "$OUT_DIR"
cp out/gds.css "$OUT_DIR/gds.css"
rm -rf "$OUT_DIR/fonts"
cp -r out/fonts "$OUT_DIR/fonts"

echo "GDS assets built:"
echo "  ${OUT_DIR}/gds.css"
echo "  ${OUT_DIR}/fonts/"
