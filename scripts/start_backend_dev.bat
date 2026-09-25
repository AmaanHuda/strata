@echo off
REM Start the STRATA backend for local development on host Python.
REM Requires PostgreSQL+PostGIS (docker compose up -d db redis) and a migrated DB
REM (scripts/run_migrations.sh). No Docker image build needed.
cd /d "%~dp0.."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 %*
