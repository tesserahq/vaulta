# Summarization Providers

## `claude`

`ClaudeSummarizationService` sends documents natively to Claude and returns a prose summary. It supports both the direct Anthropic API and AWS Bedrock.

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

Setting `BEDROCK_REGION` switches the client to Bedrock. `ANTHROPIC_API_KEY` is not needed in that mode.

**Install:**
```bash
# Direct Anthropic API
poetry add anthropic

# AWS Bedrock
poetry add boto3
```

**Default model:** `claude-sonnet-4-6`. Override by passing `model` when constructing the service (not yet exposed via `AnalysisConfig`).

**Prompt behavior:** The service uses a fixed system prompt instructing Claude to write one paragraph per major section or topic in flowing prose, focusing on key facts, parties, obligations, and important dates. The prompt is not currently configurable per-config.

---

## `modela`

Tessera-native summarization. See the dedicated [Modela](../modela.md) page.
