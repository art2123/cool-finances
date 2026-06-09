#!/bin/sh
set -e

if [ "$RUN_MODE" = "worker" ]; then
  echo "==> RUN_MODE=worker: starting ARQ reminder worker"
  exec python -m src.main worker
fi

PORT="${PORT:-8000}"
echo "==> RUN_MODE=web: starting uvicorn on port $PORT"
exec uvicorn src.api.app:app --host 0.0.0.0 --port "$PORT"
