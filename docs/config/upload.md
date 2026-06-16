# File Upload Configuration

## Size limits

| Setting | Default | Description |
|---|---|---|
| `MAX_FILE_SIZE_MB` | `100` | Maximum file size in megabytes. |
| `MAX_FILE_SIZE` | — | Override in bytes (takes precedence over `MAX_FILE_SIZE_MB`). |

Size is validated in two places:

1. **Dependency layer** (`app/routers/utils/dependencies.py`) — checked via `Content-Length` before processing begins.
2. **Service layer** (`app/services/asset_upload.py`) — re-checked after reading the actual bytes.

Both raise HTTP 413 with a message that includes the configured limit and the actual file size.

## Uvicorn server settings

Configured in `run.py` (development) and `start.sh` (production):

| Flag | Default | Description |
|---|---|---|
| `--limit-concurrency` | `1000` | Maximum simultaneous connections. |
| `--limit-max-requests` | `10000` | Restart workers after N requests (prevents memory leaks). |
| `--limit-request-line` | `8190` | Max size of the HTTP request line (URL + headers). |
| `--limit-request-fields` | `100` | Max number of HTTP headers. |
| `--limit-request-field-size` | `8190` | Max size of each HTTP header. |

## Cloudflare

Cloudflare's free and pro plans cap uploads at 100 MB, regardless of Vaulta's configuration. For larger files on enterprise plans, contact Cloudflare support to increase the limit.

## Environment examples

```bash
# Development
MAX_FILE_SIZE_MB=500

# Production (1 GB)
MAX_FILE_SIZE_MB=1000
```

## Generating a `MASTER_SECRET_KEY`

The master secret key is used to sign serve tokens for local storage URLs. Generate one with:

```bash
python3 -c 'import os; print(os.urandom(16).hex())'
```

Set as `MASTER_SECRET_KEY` in your environment or `.env` file.
