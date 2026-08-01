# Rewards Eligibility Oracle - Dockerfile
# Multi-stage build for efficient image

# ---- Stage 1: build the frontend ----
# Produces two things:
#   1. dist-ssr/entry-server.js — a self-contained SSR bundle (vite bundles the
#      GDS React components in, so the runtime needs no node_modules at all).
#   2. gds.css + Euclid Circular fonts — compiled from the GDS Tailwind preset.
FROM node:22-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build:ssr && \
    mkdir -p out && \
    npx tailwindcss -i css/entry.css -o out/gds.css --minify && \
    cp -r node_modules/@graphprotocol/gds-css/styles/fonts out/fonts

# ---- Stage 2: Python dependency builder ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (for pycryptodome)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application files
COPY generate_dashboard.py .
COPY telegram_bot.py .
COPY telegram_notifier.py .
COPY scheduler.py .
COPY database.py .

# A node binary — and nothing else from the Node world. The SSR bundle below is
# fully self-contained, so there are no node_modules to install or ship.
COPY --from=frontend-build /usr/local/bin/node /usr/local/bin/node

# The renderer: a self-contained bundle plus the two small scripts that drive it.
COPY --from=frontend-build /build/dist-ssr/entry-server.js /app/frontend/dist-ssr/entry-server.js
COPY frontend/scripts/prerender.mjs /app/frontend/scripts/prerender.mjs
COPY frontend/src/lib/data.js /app/frontend/src/lib/data.js

# GDS compiled assets (gds.css + Euclid Circular fonts) from the frontend build.
# copy_gds_assets() places these in the output dir so Caddy serves them next to
# index.html.
COPY --from=frontend-build /build/out /app/static/gds

# Create output directory for generated HTML
RUN mkdir -p /app/output

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Default command: generate dashboard once
CMD ["python", "generate_dashboard.py"]

# Health check (verify we can import dependencies)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; import Cryptodome" && node --version >/dev/null || exit 1
