#!/bin/sh
set -eu

if [ "${DATABASE_URL:-}" != "" ] && [ "${DATABASE_URL#sqlite}" = "${DATABASE_URL}" ]; then
  alembic upgrade head
fi

exec uvicorn vna_main.main:app --host 0.0.0.0 --port 8000
