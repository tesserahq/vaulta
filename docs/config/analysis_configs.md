# Analysis Config API

`AnalysisConfig` records control which analysis (and summarization) provider is used per upload. The system always maintains exactly one row with `is_default=True`.

All routes require authentication.

## List configs

```
GET /analysis-configs
```

## Get a single config

```
GET /analysis-configs/{config_id}
```

## Create a config

```
POST /analysis-configs
Content-Type: application/json

{
  "name": "Production Textract",
  "provider": "textract",
  "is_default": true,
  "provider_params": {
    "region_name": "us-west-2"
  }
}
```

Setting `is_default: true` automatically demotes the previous default.

## Update a config

```
PATCH /analysis-configs/{config_id}
Content-Type: application/json

{
  "is_default": true
}
```

Returns `409` if you attempt to demote the current default without promoting another.

## Delete a config

```
DELETE /analysis-configs/{config_id}
```

Returns `409` if you attempt to delete the active default. Promote another config first.

## Using a config on upload

Pass `config_id` as a form field on `POST /assets` to override the default for that upload:

```bash
curl -X POST http://localhost:8000/assets \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@passport.jpg" \
  -F "extract_data=true" \
  -F "config_id=<uuid>"
```

Omitting `config_id` uses the config marked `is_default=true`.

## Default invariant

Exactly one config must have `is_default=True` at all times. The repository enforces this:

- Promoting a config to default automatically demotes the previous default.
- Attempting to delete or demote the active default without a replacement raises `ValueError`, surfaced as HTTP 409.

## `provider_params` reference

`provider_params` overrides env-var settings for a specific config. See each provider's documentation for the keys it supports:

- [Analysis providers](../analysis/providers.md) — `textract`, `google_dai`, `claude` keys.
- [Modela](../modela.md) — no `provider_params`; Modela config is fully env-var driven.
