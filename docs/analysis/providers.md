# Analysis Providers

## Provider overview

| Provider key | Description | Required deps |
|---|---|---|
| `local` | Built-in barcode/OCR parser — no external API calls | — |
| `textract` | AWS Textract AnalyzeID | `boto3` |
| `google_dai` | Google Document AI | `google-cloud-documentai` |
| `claude` | Claude Vision via Anthropic API or AWS Bedrock | `anthropic` or `boto3` |
| `modela` | Tessera-native provider (analysis + summarization) | `tessera-sdk` |

The active provider is determined by the `AnalysisConfig` selected on upload. See [Analysis Config API](../config/analysis_configs.md) for managing configs.

---

## `local`

Built-in parser using barcode scanning and basic OCR. No external dependencies or network calls.

**When to use:** development, offline environments, or as a low-cost fallback when document quality is predictable.

**No additional env vars required.**

---

## `textract`

Uses AWS Textract `AnalyzeID` to extract structured fields from identity documents.

**Install:**
```bash
poetry add boto3
```

**Environment variables:**

| Variable | Required | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Yes* | AWS access key ID. |
| `AWS_SECRET_ACCESS_KEY` | Yes* | AWS secret access key. |
| `S3_REGION_NAME` | Yes | AWS region for Textract (e.g. `us-east-1`). |

\* Can be omitted if running under an IAM role with Textract permissions.

**`provider_params` overrides:**

| Key | Description |
|---|---|
| `aws_access_key_id` | Override the global AWS key. |
| `aws_secret_access_key` | Override the global AWS secret. |
| `region_name` | Override the AWS region. |

---

## `google_dai`

Uses Google Document AI for OCR and entity extraction.

**Install:**
```bash
poetry add google-cloud-documentai
```

**Environment variables:**

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_DAI_PROCESSOR_ID` | Yes | Full processor resource name, e.g. `projects/123/locations/us/processors/abc`. |
| `GOOGLE_APPLICATION_CREDENTIALS` | No | Path to a service account JSON key file. Omit to use Application Default Credentials. |

**GCP setup:**

1. Enable **Cloud Document AI API** in your GCP project.
2. Create a **Document OCR** processor (not Identity Document Proofing or Custom Document Extractor). Copy the full resource name for `GOOGLE_DAI_PROCESSOR_ID`.
3. Create a service account with the **Document AI API User** role (`roles/documentai.apiUser`).
4. Download a JSON key and set `GOOGLE_APPLICATION_CREDENTIALS` to its path.

> **Processor type note:** Use **Document OCR**. Custom Extractor processors require entity types declared in both GCP and `provider_params.entity_types`. If you see `Must have at least one entity type` in logs, switch to Document OCR or add entity types.

**`provider_params` overrides:**

| Key | Description |
|---|---|
| `processor_id` | Override `GOOGLE_DAI_PROCESSOR_ID`. |
| `credentials_path` | Override `GOOGLE_APPLICATION_CREDENTIALS`. |
| `entity_types` | Required only for Custom Document Extractor processors. List entity type names (e.g. `["invoice_id", "total"]`). |

---

## `claude`

Uses Claude Vision to analyze document images. Supports the direct Anthropic API or AWS Bedrock.

**Install:**
```bash
# Direct Anthropic API
poetry add anthropic

# AWS Bedrock
poetry add boto3
```

**Environment variables — direct API:**

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key. |

**Environment variables — AWS Bedrock:**

| Variable | Required | Description |
|---|---|---|
| `BEDROCK_REGION` | Yes | AWS region with Bedrock enabled (e.g. `us-east-1`). |
| `AWS_ACCESS_KEY_ID` | Yes* | AWS access key ID. |
| `AWS_SECRET_ACCESS_KEY` | Yes* | AWS secret access key. |

\* Can be omitted under an IAM role.

Setting `BEDROCK_REGION` switches the backend to Bedrock; `ANTHROPIC_API_KEY` is not needed in that mode.

**`provider_params` overrides:**

| Key | Description |
|---|---|
| `api_key` | Override `ANTHROPIC_API_KEY`. |
| `bedrock_region` | Use Bedrock in this region instead of the direct API. |
| `model` | Claude model ID (defaults to `claude-opus-4-5`). |

---

## `modela`

Tessera-native provider. See the dedicated [Modela](../modela.md) page.

---

## Canonical field names

Provider-specific field names are normalized to the following canonical names. Fields with no canonical mapping are included under their raw snake_cased key, so no data is silently dropped.

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
