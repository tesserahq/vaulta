# Architecture

Vaulta is organized into four independent layers. Each layer has a base class (ABC), one or more concrete implementations, and a factory or service that instantiates the right implementation based on configuration.

## Layer map

```
app/
├── storage/
│   ├── base.py          StorageBackend ABC
│   ├── local.py         LocalStorageBackend
│   ├── s3.py            S3StorageBackend
│   └── factory.py       StorageFactory (singleton)
│
├── services/
│   ├── analysis/
│   │   ├── base.py      DocumentAnalysisBackend ABC, AnalysisResult, FieldValue, OcrLine
│   │   ├── local.py     LocalAnalysisBackend
│   │   ├── textract.py  TextractAnalysisBackend
│   │   ├── google_dai.py GoogleDAIAnalysisBackend
│   │   ├── claude_vision.py ClaudeVisionAnalysisBackend
│   │   ├── preprocessor.py  Image normalization (JPEG resize)
│   │   └── factory.py   AnalysisFactory (singleton)
│   │
│   ├── summarization/
│   │   └── claude.py    ClaudeSummarizationService, SummaryResult
│   │
│   ├── processors/
│   │   ├── base.py      AssetProcessor ABC, ProcessorContext
│   │   ├── analysis.py  AnalysisProcessor
│   │   ├── summarization.py SummarizationProcessor
│   │   └── modela.py    ModelaAnalysisProcessor, ModelaSummarizationProcessor
│   │
│   └── asset_upload.py  upload_asset() — orchestrates storage + processors
│
├── providers.py         StorageProvider / AnalysisProvider enums
├── models/
│   └── analysis_config.py  AnalysisConfig ORM model
└── repositories/
    └── analysis_config_repository.py
```

## Storage layer

`StorageBackend` is the only layer without per-upload configuration. The backend is selected once at startup via `STORAGE_BACKEND` (`local` or `s3`) and cached as a singleton by `StorageFactory`.

The local backend writes files to a private directory and issues signed serve tokens. The S3 backend stores files in a bucket and returns presigned URLs.

## Analysis layer

`DocumentAnalysisBackend.analyze(file_bytes, content_type)` returns an `AnalysisResult` with structured fields, OCR lines, document type, and a raw provider response.

Before calling a provider, `preprocessor.py` normalises the input to a JPEG resized to `ANALYSIS_MAX_IMAGE_PX` on its longest side. PDFs are rasterized to a JPEG of the first page.

`AnalysisFactory` caches a singleton for the default provider. When a non-default `AnalysisConfig` is used (different provider or `provider_params`), it always creates a fresh instance so per-config overrides are respected.

## Summarization layer

`ClaudeSummarizationService.summarize(file_bytes, content_type)` sends the file as a native Claude content block (document block for PDFs, image block for images) and returns a `SummaryResult` with the prose text, provider name, and model ID.

There is no factory singleton for summarization — a new service instance is created per request in the router.

## Processor layer

`AssetProcessor` is the composition point. Each processor wraps a backend or service and implements `process(file_bytes, content_type, asset_url, ctx) → dict`. The dict is a partial `AssetUpdate` payload; `upload_asset()` merges results from all processors before writing the final update.

`ProcessorContext` carries `user_id` and `project_id`, which Modela processors use for token exchange and API calls.

## Factory singleton pattern

Both `StorageFactory` and `AnalysisFactory` hold a class-level `_instance`. Call `.reset()` in test teardown when you patch settings, otherwise the cached instance will carry stale config across tests.

## AnalysisConfig

An `AnalysisConfig` row in the database selects which analysis (and, separately, which summarization) provider to use for a given upload. Exactly one row must have `is_default=True` at all times — the repository enforces this invariant and raises `ValueError` (surfaced as HTTP 409) if a request would violate it.

The `config_id` form field on `POST /assets` overrides the default for that specific upload. When omitted, the default config is used.
