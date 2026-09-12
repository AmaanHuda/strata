#!/bin/bash
# Run Alembic migrations
set -e
echo "Running migrations..."
alembic upgrade head
echo "Migrations complete."
