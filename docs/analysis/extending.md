# Adding an Analysis Provider

Implement a new `DocumentAnalysisBackend`, register it in the factory, and add a provider key.

## 1. Implement the ABC

Create a file under `app/services/analysis/`:

```python
# app/services/analysis/my_provider.py
from app.services.analysis.base import AnalysisResult, DocumentAnalysisBackend


class MyProviderAnalysisBackend(DocumentAnalysisBackend):
    def __init__(self, api_key: str, max_image_px: int = 2048) -> None:
        self._api_key = api_key
        self._max_image_px = max_image_px

    async def analyze(self, file_bytes: bytes, content_type: str) -> AnalysisResult:
        # Preprocess the image (normalize to JPEG, resize)
        from app.services.analysis.preprocessor import preprocess_image
        jpeg_bytes = preprocess_image(file_bytes, content_type, self._max_image_px)

        # Call the external API ...
        raw = await _call_my_api(jpeg_bytes, self._api_key)

        return AnalysisResult(
            document_type="passport",
            document_type_confidence=raw["type_confidence"],
            provider="my_provider",
            fields={
                "given_names": FieldValue(value=raw["first_name"], confidence=0.95),
            },
            ocr_lines=[],
            raw_response=raw,
        )
```

**Lazy imports:** keep any SDK import (`import my_sdk`) inside `__init__` or the method body, not at module level. This lets the app start even if the optional package is not installed.

## 2. Add a provider key

```python
# app/providers.py
class AnalysisProvider(StrEnum):
    LOCAL = "local"
    TEXTRACT = "textract"
    GOOGLE_DAI = "google_dai"
    CLAUDE = "claude"
    MODELA = "modela"
    MY_PROVIDER = "my_provider"  # add this
```

## 3. Register in the factory

```python
# app/services/analysis/factory.py  — inside _create_backend()
if provider == AnalysisProvider.MY_PROVIDER:
    from app.services.analysis.my_provider import MyProviderAnalysisBackend
    return MyProviderAnalysisBackend(
        api_key=params.get("api_key") or settings.my_provider_api_key,
        max_image_px=settings.analysis_max_image_px,
    )
```

## 4. Add settings (if needed)

```python
# app/config.py
my_provider_api_key: str = Field(default="", validation_alias="MY_PROVIDER_API_KEY")
```

## 5. Verify

Create an `AnalysisConfig` with `provider="my_provider"` and upload a test document:

```bash
curl -X POST http://localhost:8000/analysis-configs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Provider", "provider": "my_provider"}'

curl -X POST http://localhost:8000/assets \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.jpg" \
  -F "extract_data=true" \
  -F "config_id=<uuid>"
```
