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
# --limit-request-line 8190: Maximum size of HTTP request line in bytes (URL + headers)
# --limit-request-fields 100: Maximum number of HTTP headers (important for multipart uploads)
# --limit-request-field-size 8190: Maximum size of each HTTP header in bytes
uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --limit-concurrency 1000 \
    --limit-max-requests 10000 \
    --limit-request-line 8190 \
    --limit-request-fields 100 \
    --limit-request-field-size 8190
