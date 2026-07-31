# Rewards Eligibility Oracle - Dockerfile
# Multi-stage build for efficient image

# ---- Stage 1: build The Graph Design System (GDS) stylesheet ----
# Compiles gds.css (Tailwind v4 + @graphprotocol/gds-css) so the dashboard can
# consume GDS design tokens and the light/dark theme classes. The Python file is
# COPYed in purely so Tailwind's @source scanner can read it as plain text and
# emit the semantic tokens referenced from the hand-written <style> block.
FROM node:22-slim AS gds-build
WORKDIR /build
RUN npm install tailwindcss@^4 @tailwindcss/cli @graphprotocol/gds-css --no-audit --no-fund
COPY generate_dashboard.py .
RUN mkdir -p src out && \
    printf "@import 'tailwindcss';\n@import '@graphprotocol/gds-css';\n@source '../generate_dashboard.py';\n" > src/entry.css && \
    npx @tailwindcss/cli -i src/entry.css -o out/gds.css
RUN cp -r node_modules/@graphprotocol/gds-css/styles/fonts out/fonts

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

# GDS compiled assets (gds.css + Euclid Circular fonts) from the gds-build stage.
# main() copies these into the output dir so Caddy serves them next to index.html.
COPY --from=gds-build /build/out /app/static/gds

# Create output directory for generated HTML
RUN mkdir -p /app/output

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Default command: generate dashboard once
CMD ["python", "generate_dashboard.py"]

# Health check (verify we can import dependencies)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; import Cryptodome; print('OK')" || exit 1
