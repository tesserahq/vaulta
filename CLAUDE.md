# Vaulta

FastAPI asset management service. Python 3.14, PostgreSQL, SQLAlchemy, Alembic, Pydantic v2.

## Commands

```bash
poetry run dev          # Start dev server with hot reload (port 8000)
poetry run pytest       # Run tests
alembic upgrade head    # Apply migrations
alembic revision --autogenerate -m "description"  # Generate a new migration
ruff check .            # Lint
black .                 # Format
```

## Architecture

```
app/
  config.py             # All settings (pydantic-settings, reads from .env)
  main.py               # create_app() factory used by tests and production
  db.py                 # SQLAlchemy engine, Base, get_db dependency
  models/               # SQLAlchemy ORM models
  schemas/              # Pydantic request/response models
  repositories/         # DB access layer (one class per model)
  routers/              # FastAPI route handlers
    utils/dependencies.py  # Shared Depends helpers
  services/
    asset_upload.py     # Core upload logic
    analysis/           # Pluggable document analysis providers
      base.py           # ABC + AnalysisResult types
      factory.py        # AnalysisFactory singleton (mirrors StorageFactory)
      local.py / textract.py / google_dai.py / claude_vision.py
  storage/              # Pluggable storage backends (local, S3)
    factory.py          # StorageFactory singleton
tests/
  conftest.py           # Fixtures: real Postgres, transaction rollback, mock auth
  fixtures/             # user_fixtures, asset_fixtures, client_fixtures
```

## Environment

Required in all environments:
```bash
MASTER_SECRET_KEY=<hex>   # Used for signed URLs; generate with: python3 -c 'import os; print(os.urandom(16).hex())'
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vaulta
```

Tests use a separate database — set `ENV=test` (or `ENVIRONMENT=test`) to activate it. The test suite creates `vaulta_test` automatically if it doesn't exist.

See `docs/document_analysis.md` for provider-specific env vars (Textract, Google DAI, Claude).

## Testing

Tests use a real PostgreSQL database with transaction rollback — no mocks for the DB layer. Each test function gets a fresh transaction that's rolled back at teardown.

Auth is bypassed in tests via `MockAuthenticationMiddleware`; the test user is injected through `app.state.test_user`. Use the `client` fixture (not `TestClient` directly) to get this wiring automatically.

## Key Patterns

**Factory singletons** — `StorageFactory` and `AnalysisFactory` cache a singleton instance. Call `.reset()` in test teardown when you need a fresh instance (e.g. after patching settings).

**`get_analysis_backend` is a plain function, not a `Depends`** — because it takes a `config_id` Form param alongside other Form fields, which FastAPI can't inject via `Depends`. It's called directly in the route handler body.

**AnalysisConfig default invariant** — exactly one row must have `is_default=True` at all times. The repository enforces this; attempting to demote the active default raises `ValueError` (surfaced as HTTP 409).

**Lazy provider imports** — all cloud SDK imports (`boto3`, `google.cloud`, `anthropic`) are deferred to `__init__` so the app starts even if optional deps aren't installed.
