# Summarization

Summarization generates a prose summary of an uploaded document. It is triggered by passing `summarize=true` on `POST /assets`.

## Output shape

A successful summarization populates `asset.summary`:

```json
{
  "text": "This is a rental agreement between Jane Smith and Acme Properties LLC, dated March 1, 2025...",
  "provider": "claude",
  "model": "claude-sonnet-4-6"
}
```

- **`text`** — the full prose summary. One paragraph per major section or topic, written in flowing prose (no bullet points or headers).
- **`provider`** — the backend that generated the summary (`"claude"` or `"modela"`).
- **`model`** — the model ID used.

## How the provider is selected

1. The caller optionally passes `config_id` on upload.
2. The router resolves the `AnalysisConfig` (same record used for analysis).
3. If `config.summarization_provider == "modela"`, a `ModelaSummarizationProcessor` is used — see [Modela](../modela.md).
4. Otherwise, a `SummarizationProcessor` wrapping `ClaudeSummarizationService` is used.

Note that analysis and summarization each read their provider from a different field on `AnalysisConfig` (`provider` vs `summarization_provider`), so they can be mixed independently per config.

## Document handling

`ClaudeSummarizationService` sends the file as a native Claude content block:

- **PDF** → `document` block with base64-encoded bytes. The full document is sent; no rasterization occurs.
- **Image** → `image` block with base64-encoded bytes and the original MIME type.

This differs from the analysis pipeline, which always converts to JPEG before calling a provider.
