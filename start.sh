#!/bin/bash
set -e

echo "🔧 Running Alembic migrations..."
alembic upgrade head

echo "🚀 Starting Vaulta..."

# Start FastAPI application
PORT=${PORT:-8000}

# Uvicorn configuration for file uploads and performance:
# --host 0.0.0.0: Bind to all network interfaces
# --port $PORT: Use PORT environment variable or default to 8000
# --limit-concurrency 1000: Maximum number of concurrent connections (prevents server overload)
# --limit-max-requests 10000: Restart workers after this many requests (prevents memory leaks)
# --limit-request-fields 100: Maximum number of HTTP headers (important for multipart uploads)
uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --limit-concurrency 1000 \
    --limit-max-requests 10000
