# Document Analysis Configuration Guide

Vaulta can extract structured data from uploaded identity documents (passports, driver's licenses, national IDs) using a pluggable provider system. Each upload can use a different provider by referencing an `AnalysisConfig` record.

## How it works

1. When you upload a file with `extract_data=true`, Vaulta selects a provider backend.
2. The file is normalized to a JPEG (resized to `ANALYSIS_MAX_IMAGE_PX` on the longest side) and sent to the provider.
3. The provider returns structured fields (given names, surname, date of birth, document number, etc.) which are stored on the asset record as `extracted_data`.

## Providers

| Provider key | Description | Required deps |
|---|---|---|
| `local` | Built-in barcode/OCR parser (no external API calls) | — |
| `textract` | AWS Textract AnalyzeID | `boto3` |
| `google_dai` | Google Document AI | `google-cloud-documentai` |
| `claude` | Claude Vision via Anthropic API or AWS Bedrock | `anthropic` or `boto3` |

## Environment Variables

### Global settings

| Variable | Default | Description |
|---|---|---|
| `ANALYSIS_BACKEND` | `local` | Default provider when no `AnalysisConfig` is matched. One of: `local`, `textract`, `google_dai`, `claude`. |
| `ANALYSIS_MAX_IMAGE_PX` | `2048` | Maximum pixel dimension (longest side) images are resized to before sending to a provider. |

### AWS Textract

Textract reuses the same AWS credentials used for S3 storage.

| Variable | Required | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Yes* | AWS access key ID. |
| `AWS_SECRET_ACCESS_KEY` | Yes* | AWS secret access key. |
| `S3_REGION_NAME` | Yes | AWS region where Textract will be called (e.g. `us-east-1`). |

\* Can be omitted if the process runs under an IAM role with Textract permissions.

### Google Document AI

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_DAI_PROCESSOR_ID` | Yes | Full processor resource name, e.g. `projects/123/locations/us/processors/abc`. |
| `GOOGLE_APPLICATION_CREDENTIALS` | No | Path to a service account JSON key file. Omit to use Application Default Credentials. |

### Claude Vision (Anthropic API)

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key from console.anthropic.com. |

### Claude Vision (AWS Bedrock)

Set `BEDROCK_REGION` to use Claude via Bedrock instead of the direct Anthropic API. `ANTHROPIC_API_KEY` is not needed in this mode; Bedrock uses standard AWS credentials.

| Variable | Required | Description |
|---|---|---|
| `BEDROCK_REGION` | Yes | AWS region where Bedrock is enabled (e.g. `us-east-1`). |
| `AWS_ACCESS_KEY_ID` | Yes* | AWS access key ID. |
| `AWS_SECRET_ACCESS_KEY` | Yes* | AWS secret access key. |

\* Can be omitted if running under an IAM role.

## Setup

### 1. Install optional dependencies

```bash
# AWS Textract or Bedrock
poetry add boto3

# Google Document AI
poetry add google-cloud-documentai

# Claude via Anthropic API
poetry add anthropic

# PDF support (required if users upload PDFs for analysis)
poetry add pdf2image
```

### 2. Run the migration

```bash
alembic upgrade head
```

This creates the `analysis_configs` table and seeds a default row using the `local` provider.

## AnalysisConfig API

Configs are managed via `/analysis-configs`. All routes require authentication.

### List all configs

```
GET /analysis-configs
```

### Get a single config

```
GET /analysis-configs/{config_id}
```

### Create a config

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

Setting `is_default: true` automatically demotes the previous default. The system always maintains exactly one default config.

### Update a config

```
PATCH /analysis-configs/{config_id}
Content-Type: application/json

{
  "is_default": true
}
```

Returns `409` if you attempt to demote the current default without promoting another.

### Delete a config

```
DELETE /analysis-configs/{config_id}
```

Returns `409` if you attempt to delete the active default. Promote another config first.

## Using a config on upload

Pass `config_id` as a form field when uploading to override the default provider for that specific upload:

```bash
curl -X POST "http://localhost:8000/assets" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@passport.jpg" \
  -F "extract_data=true" \
  -F "config_id=<uuid-of-your-config>"
```

Omitting `config_id` uses the config marked `is_default=true`.

## provider_params reference

`provider_params` on an `AnalysisConfig` row can override any setting for that specific config. These values take precedence over environment variables.

### textract

| Key | Description |
|---|---|
| `aws_access_key_id` | Override the global AWS key ID. |
| `aws_secret_access_key` | Override the global AWS secret. |
| `region_name` | Override the AWS region. |

### google_dai

| Key | Description |
|---|---|
| `processor_id` | Override `GOOGLE_DAI_PROCESSOR_ID`. |
| `credentials_path` | Override `GOOGLE_APPLICATION_CREDENTIALS`. |

### claude

| Key | Description |
|---|---|
| `api_key` | Override `ANTHROPIC_API_KEY`. |
| `bedrock_region` | Use Bedrock in this region instead of the direct API. |
| `model` | Claude model ID to use (defaults to `claude-opus-4-5`). |

## Extracted data format

A successful extraction stores a JSON object on the asset under `extracted_data`:

```json
{
  "document_type": "passport",
  "document_type_confidence": 0.98,
  "partial": false,
  "provider": "textract",
  "fields": {
    "given_names":     { "value": "Jane",       "confidence": 0.99 },
    "surname":         { "value": "Smith",       "confidence": 0.99 },
    "date_of_birth":   { "value": "1990-05-15",  "confidence": 0.97 },
    "expiration_date": { "value": "2030-05-14",  "confidence": 0.98 },
    "document_number": { "value": "AB1234567",   "confidence": 0.99 }
  }
}
```

`partial: true` indicates that one or more expected fields for the detected document type were missing from the response.

### Canonical field names

All providers normalize their output to these field names:

| Field | Description |
|---|---|
| `given_names` | First / given name(s) |
| `surname` | Family / last name |
| `middle_name` | Middle name (Textract only) |
| `date_of_birth` | Date of birth |
| `expiration_date` | Document expiry date |
| `document_number` | ID / passport / license number |
| `address` | Registered address |
| `sex` | Sex (Google DAI only) |
| `nationality` | Nationality (Google DAI only) |

## Supported input formats

| Format | Notes |
|---|---|
| JPEG / JPG | Native; no conversion. |
| PNG | Converted to JPEG before submission. |
| GIF | First frame extracted and converted to JPEG. |
| PDF | First page rendered at 300 DPI and converted to JPEG. Requires `pdf2image` and `poppler`. |
