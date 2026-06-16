# Document Analysis Configuration Guide

Vaulta can extract structured data from uploaded documents (passports, driver's licenses, national IDs, credit cards, and more) using a pluggable provider system. Each upload can use a different provider by referencing an `AnalysisConfig` record.

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

`GOOGLE_APPLICATION_CREDENTIALS` (or `credentials_path` in `provider_params`) must point to a **service account JSON key** downloaded from Google Cloud—not a user OAuth token.

#### GCP setup

1. **Create or select a project** in the [Google Cloud Console](https://console.cloud.google.com/).

2. **Enable the API** — APIs & Services → Library → search **Cloud Document AI API** → Enable.

3. **Create a processor** — go to the [Document AI processors page](https://console.cloud.google.com/ai/document-ai/processors) and create a **Document OCR** processor. Copy the full resource name for `GOOGLE_DAI_PROCESSOR_ID`, e.g. `projects/123456789/locations/us/processors/abcdef123456`. Processors must be in a [supported region](https://cloud.google.com/document-ai/docs/regions) (commonly `us` or `eu` in the path).

   > **Processor type:** Use **Document OCR** (not Identity Document Proofing or Custom Document Extractor). Document OCR does not require entity types to be declared upfront and returns all detected text via the OCR layer, which Vaulta surfaces in `ocr_lines`. Structured `fields` are extracted from the entities the processor returns. Custom Extractor processors require entity types to be configured both in GCP and in `provider_params` before they will accept requests.

4. **Create a service account** — IAM & Admin → Service Accounts → Create service account (e.g. `vaulta-document-ai`).

5. **Grant permissions** — Assign a role that can call Document AI on your project, for example **Document AI API User** (`roles/documentai.apiUser`).

6. **Download a JSON key** — Open the service account → Keys → Add key → Create new key → JSON. Store the file securely; treat it like a password.

7. **Configure Vaulta** — set the path to that file and your processor ID:

   ```bash
   GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
   GOOGLE_DAI_PROCESSOR_ID=projects/.../locations/us/processors/...
   ```

   Or pass overrides per `AnalysisConfig` via `provider_params` (`credentials_path`, `processor_id`).

If you omit `GOOGLE_APPLICATION_CREDENTIALS`, the Google client uses **Application Default Credentials** (e.g. `gcloud auth application-default login` locally, or the metadata service on GCE/GKE/Cloud Run).

Document AI is billed per processed page; ensure billing is enabled on the project.

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

### Modela

Modela is a Tessera-native document analysis and summarization provider. Calls are attributed to the requesting user via a delegated token obtained through a machine-to-machine token exchange.

| Variable | Required | Description |
|---|---|---|
| `MODELA_API_URL` | Yes | Base URL of the Modela API (configured in `tessera-sdk` settings). |
| `MODELA_AUDIENCE` | Yes | Token exchange audience for Modela (e.g. `https://modela.tessera.com`). |
| `MODELA_SCOPE` | Yes | Scopes to request during token exchange (e.g. `scan:file summarize:file`). |

M2M credentials (`service_account_client_id` / `service_account_client_secret`) must also be set in the tessera-sdk settings so the M2M token client can obtain a base token before exchanging it.

## Setup

### 1. Install optional dependencies

```bash
# AWS Textract or Bedrock
poetry add boto3

# Google Document AI (see GCP setup under Google Document AI above)
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
| `entity_types` | Required only for **Custom Document Extractor** processors. List the entity type names that were defined in your processor schema (e.g. `["invoice_id", "total"]`). Not needed for Document OCR. |

If you see `Must have at least one entity type` in the logs, your processor is a Custom Document Extractor — either switch to a **Document OCR** processor, or list the expected entity types in `provider_params.entity_types`.

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
  "provider": "textract",
  "fields": {
    "given_names":     { "value": "Jane",       "confidence": 0.99 },
    "surname":         { "value": "Smith",       "confidence": 0.99 },
    "date_of_birth":   { "value": "1990-05-15",  "confidence": 0.97 },
    "expiration_date": { "value": "2030-05-14",  "confidence": 0.98 },
    "document_number": { "value": "AB1234567",   "confidence": 0.99 },
    "city":            { "value": "Springfield", "confidence": 0.95 }
  },
  "ocr_lines": [
    { "text": "JANE SMITH",    "confidence": 0.99 },
    { "text": "1990-05-15",   "confidence": 0.97 },
    { "text": "AB1234567",    "confidence": 0.99 }
  ]
}
```

- **`fields`** — structured key/value pairs. Where a provider returns a well-known field type (e.g. `FIRST_NAME`, `family_name`), Vaulta normalises it to a canonical name. Any field the provider returns that has no canonical mapping is included under its raw snake_cased key. Only non-empty values are included.
- **`ocr_lines`** — every line of text detected on the document, in order. This captures values (card numbers, phone numbers, free-form text) that may not appear in `fields`. Confidence is provider-native where available; `1.0` is used as a placeholder for Google DAI.
- **`document_type`** — a free string. Well-known types are normalised (e.g. `"DRIVER LICENSE FRONT"` → `"drivers_license"`); unrecognised types are passed through as snake_case.

### Canonical field names

The following field names are used when a provider returns a recognised field type. Any provider-specific field not listed here is included in `fields` under its raw snake_cased key, so no data is silently dropped.

| Field | Description | Providers |
|---|---|---|
| `given_names` | First / given name(s) | all |
| `surname` | Family / last name | all |
| `middle_name` | Middle name | Textract, Claude |
| `date_of_birth` | Date of birth | all |
| `expiration_date` | Document expiry date | all |
| `document_number` | ID / passport / license number | all |
| `address` | Registered address | all |
| `city` | City from address | Textract |
| `state` | State from address | Textract |
| `postal_code` | Postal / ZIP code | Textract |
| `state_name` | Full state name | Textract |
| `county` | County | Textract |
| `place_of_birth` | Place of birth | Textract |
| `suffix` | Name suffix | Textract |
| `class` | License class | Textract |
| `restrictions` | License restrictions | Textract |
| `endorsements` | License endorsements | Textract |
| `veteran` | Veteran indicator | Textract |
| `mrz_code` | Machine-readable zone | Textract |
| `sex` | Sex | Google DAI, Claude |
| `nationality` | Nationality | Google DAI, Claude |
| `issuing_state` | Issuing country/state | Google DAI, Claude |

## Supported input formats

| Format | Notes |
|---|---|
| JPEG / JPG | Native; no conversion. |
| PNG | Converted to JPEG before submission. |
| GIF | First frame extracted and converted to JPEG. |
| PDF | First page rendered at 300 DPI and converted to JPEG. Requires `pdf2image` and `poppler`. |
