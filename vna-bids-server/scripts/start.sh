#!/bin/sh
set -eu

alembic upgrade head

exec uvicorn bids_server.main:app --host 0.0.0.0 --port 8080
