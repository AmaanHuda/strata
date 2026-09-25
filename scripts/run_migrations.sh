#!/usr/bin/env bash
# Run Alembic migrations up to head.
# Uses `python -m alembic` so it works even when the alembic console script
# is not on PATH (common inside virtualenvs / containers).
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python}"

echo "Running migrations (alembic upgrade head)..."
"${PYTHON_BIN}" -m alembic upgrade head
echo "Migrations complete."
