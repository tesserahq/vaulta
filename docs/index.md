# Vaulta

Vaulta is a FastAPI-based asset management service. It handles file storage, document data extraction (OCR / AI analysis), and document summarization through a pluggable provider architecture.

## Upload pipeline

Every file upload runs through the same pipeline:

```
POST /assets
  │
  ├─ Validate file size
  ├─ Create asset record (state: PENDING → UPLOADING)
  ├─ Save file to storage backend (local or S3)
  ├─ Obtain public URL from storage
  │
  ├─ [if extract_data=true]  run AnalysisProcessor or ModelaAnalysisProcessor
  ├─ [if summarize=true]     run SummarizationProcessor or ModelaSummarizationProcessor
  │
  ├─ Merge processor results into asset record
  └─ Return AssetUploadResponse (state: COMPLETED)
```

Processors are composable: a single upload can run analysis and summarization in sequence. Each processor returns a partial dict that is merged into the final `AssetUpdate`.

## Key concepts

| Concept | What it is |
|---|---|
| **StorageBackend** | Saves and retrieves raw files (local disk or S3). |
| **DocumentAnalysisBackend** | Extracts structured fields from a document image (OCR / AI). |
| **AssetProcessor** | Thin wrapper that calls a backend and returns a partial update dict. |
| **ClaudeSummarizationService** | Sends a document to Claude and returns a prose summary. |
| **AnalysisConfig** | DB record that selects which analysis provider to use per upload. |
| **AnalysisFactory / StorageFactory** | Singleton factories that cache backend instances. |

## Navigation

- **[Architecture](architecture.md)** — how the layers connect and which files implement what.
- **[Analysis](analysis/index.md)** — document data extraction: providers, config, output format.
- **[Summarization](summarization/index.md)** — prose summarization via Claude.
- **[Processors](processors/index.md)** — the `AssetProcessor` abstraction that wires backends into the upload pipeline.
- **[Modela](modela.md)** — Tessera-native provider covering both analysis and summarization.
- **[Configuration](config/upload.md)** — file size limits, env vars, server tuning.
- **[Development](development.md)** — commands, test setup, migrations.
