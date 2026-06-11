# Development

## Commands

```bash
poetry run dev          # Start dev server with hot reload (port 8000)
poetry run pytest       # Run all tests
alembic upgrade head    # Apply pending migrations
alembic revision --autogenerate -m "description"  # Generate a new migration
ruff check .            # Lint
black .                 # Format
```

## Environment

Required in all environments:

```bash
MASTER_SECRET_KEY=<hex>   # Generate: python3 -c 'import os; print(os.urandom(16).hex())'
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vaulta
```

See [File Upload Configuration](config/upload.md) and [Analysis Providers](analysis/providers.md) for provider-specific env vars.

## Tests

Tests use a real PostgreSQL database — no mocks for the DB layer. Each test function gets a fresh transaction that is rolled back at teardown.

The test suite creates `vaulta_test` automatically if it does not exist. Set `ENV=test` (or `ENVIRONMENT=test`) to activate the test database URL.

Authentication is bypassed in tests via `MockAuthenticationMiddleware`. The test user is injected through `app.state.test_user`. Use the `client` fixture (not `TestClient` directly) to get this wiring automatically.

### Factory singletons in tests

`StorageFactory` and `AnalysisFactory` cache a singleton instance. If a test patches settings (e.g. to swap providers), call `.reset()` in teardown so the next test gets a fresh instance:

```python
def teardown_function():
    AnalysisFactory.reset()
    StorageFactory.reset()
```

## Project structure

```
app/
  config.py             # All settings (pydantic-settings, reads from .env)
  main.py               # create_app() factory
  db.py                 # SQLAlchemy engine, Base, get_db dependency
  providers.py          # StorageProvider / AnalysisProvider enums
  models/               # SQLAlchemy ORM models
  schemas/              # Pydantic request/response models
  repositories/         # DB access layer (one class per model)
  routers/              # FastAPI route handlers
    utils/dependencies.py  # Shared Depends helpers
  services/
    asset_upload.py     # Core upload orchestration
    analysis/           # DocumentAnalysisBackend implementations + factory
    summarization/      # ClaudeSummarizationService
    processors/         # AssetProcessor implementations
  storage/              # StorageBackend implementations + factory
tests/
  conftest.py           # Fixtures: real Postgres, transaction rollback, mock auth
  fixtures/             # user_fixtures, asset_fixtures, client_fixtures
```
