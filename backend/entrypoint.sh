#!/bin/sh
set -e

alembic upgrade head

if [ "$SEED_ON_START" = "true" ]; then
  python -m app.seed
fi

# Most PaaS hosts (Render included) assign the port at deploy time via $PORT
# and expect the app to bind to it; local/Docker Compose runs fall back to 8000.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
