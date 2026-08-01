# VisualFind backend (FastAPI). See docker-compose.yml for the full stack
# (backend + frontend) and README.md#docker for usage.

FROM python:3.11-slim AS base

WORKDIR /app

# System deps: only what's needed to install Python packages and (optionally)
# Playwright's browser binary for Tier-3 price extraction.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tier-3 (headless browser) price extraction needs Playwright's Chromium
# binary, which is a large download. Off by default to keep the image small
# and the build fast - matches ENABLE_HEADLESS_BROWSER_FALLBACK=false being
# the safe default for constrained/free-tier hosts (see render.yaml). Build
# with `--build-arg INSTALL_PLAYWRIGHT_BROWSER=true` to include it.
ARG INSTALL_PLAYWRIGHT_BROWSER=false
RUN if [ "$INSTALL_PLAYWRIGHT_BROWSER" = "true" ]; then \
        playwright install --with-deps chromium; \
    fi

COPY app ./app
COPY static ./static

EXPOSE 8000

# Uses $PORT if the platform provides one (Render/Railway/Fly all do),
# falling back to 8000 for plain `docker run`.
ENV PORT=8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
