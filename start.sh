#!/bin/bash
set -e

echo "🔧 Running Alembic migrations..."
alembic upgrade head

echo "🚀 Starting Quore..."

# Start FastAPI application
uvicorn app.main:app --host 0.0.0.0 --port 8000
