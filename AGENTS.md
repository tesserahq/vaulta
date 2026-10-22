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

Local Postgres and Redis run in Docker containers that the developer starts. Do not install, start, or stop them (no `brew install`, `brew services`, or `docker run` for them). If they are unreachable, tell the developer and stop; do not try to fix the services yourself.

Tests use a separate database — set `ENV=test` (or `ENVIRONMENT=test`) to activate it. The database must already exist (`createdb vaulta_test`): `tests/conftest.py`'s `ensure_test_database()` connects *to* `vaulta_test` in order to create it, so it can't bootstrap a missing one.

See `docs/document_analysis.md` for provider-specific env vars (Textract, Google DAI, Claude).

## Testing

Tests use a real PostgreSQL database with transaction rollback — no mocks for the DB layer. Each test function gets a fresh transaction that's rolled back at teardown.

Auth is bypassed in tests via `MockAuthenticationMiddleware`; the test user is injected through `app.state.test_user`. Use the `client` fixture (not `TestClient` directly) to get this wiring automatically.

## Key Patterns

**Factory singletons** — `StorageFactory` and `AnalysisFactory` cache a singleton instance. Call `.reset()` in test teardown when you need a fresh instance (e.g. after patching settings).

**`get_analysis_backend` is a plain function, not a `Depends`** — because it takes a `config_id` Form param alongside other Form fields, which FastAPI can't inject via `Depends`. It's called directly in the route handler body.

**AnalysisConfig default invariant** — exactly one row must have `is_default=True` at all times. The repository enforces this; attempting to demote the active default raises `ValueError` (surfaced as HTTP 409).

**Serve URLs are a public contract** — `serve_url`s (`/assets/serve/{asset_id}.{client_id}.{expires_at}.{hmac}`, minted on upload when `expires_in` is passed, capped by `MAX_SERVE_URL_EXPIRY`) are embedded in emails that have already been sent (looply-portal, sendly-portal). Changing the route, the payload/signature format or `derive_secret`, or rotating `MASTER_SECRET_KEY`, breaks every image in those emails until they expire. The S3 branch streams bytes through Vaulta and must never return an upstream S3 error as a cacheable 200 — successful responses are `Cache-Control: immutable` (see #152, and #153 for the CloudFront plan).

**Lazy provider imports** — all cloud SDK imports (`boto3`, `google.cloud`, `anthropic`) are deferred to `__init__` so the app starts even if optional deps aren't installed.

## Shared Tessera docs

Cross-service knowledge lives in [tesserahq/docs](https://github.com/tesserahq/docs) (locally `~/sites/tesserahq/docs` when available): the glossary, service ownership, and Custos authorization conventions. Read it before writing or reviewing a PRD, or changing authorization, project scoping, or asset classification.

Update those docs whenever you learn something important that other Tessera services or products would need to know, for example:

- A term is used differently in code, a PRD, or another service than in the glossary.
- A Custos domain, resolver, or permission convention is confirmed, changed, or found to be inconsistent.
- A service's responsibility changes, or a new cross-service contract is added.
- An open decision in `docs/authorization.md` or `docs/services.md` is resolved.

Keep Vaulta-specific detail (routes, schema, migrations) in this repo's docs and PRDs. Shared docs should describe the platform and stay product-agnostic. Make the change on a branch in the docs repo and open a PR; do not push to its `main`. Mention the docs change in your final message so the user can review it.

## Database migrations

- Migrations run only in the API's `start.sh`. During a deploy, old and new containers overlap (the API rolls; workers deploy separately), so every migration must work with the previous release's code.
- One release: additive changes (nullable column or one with a server default, table, index).
- Two releases: dropping or renaming a column or table, adding `NOT NULL`, or changing a type. Release 1 stops reading and writing it; a later release runs the migration.
- See [Database migrations](https://github.com/mylinden-tech/infra/blob/main/docs/linden-continuous-delivery.md#database-migrations) and mylinden-tech/infra#260.
