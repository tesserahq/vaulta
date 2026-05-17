from typing import Optional

from app.services.analysis.base import DocumentAnalysisBackend

_VALID_PROVIDERS = ("local", "textract", "google_dai", "claude")


class AnalysisFactory:
    """Singleton factory for DocumentAnalysisBackend instances.

    get_backend() with no arguments returns a cached singleton for the default provider
    (read from settings.analysis_backend). Passing provider/params always creates a
    fresh instance so per-config overrides are respected.
    """

    _instance: Optional[DocumentAnalysisBackend] = None

    @classmethod
    def get_backend(
        cls,
        provider: Optional[str] = None,
        params: Optional[dict] = None,
    ) -> DocumentAnalysisBackend:
        if provider is None and not params:
            if cls._instance is None:
                from app.config import get_settings

                cls._instance = cls._create_backend(get_settings().analysis_backend, {})
            return cls._instance
        from app.config import get_settings

        return cls._create_backend(
            provider or get_settings().analysis_backend, params or {}
        )

    @classmethod
    def _create_backend(cls, provider: str, params: dict) -> DocumentAnalysisBackend:
        from app.config import get_settings

        settings = get_settings()

        if provider == "local":
            from app.services.analysis.local import LocalAnalysisBackend

            return LocalAnalysisBackend()

        elif provider == "textract":
            from app.services.analysis.textract import TextractAnalysisBackend

            return TextractAnalysisBackend(
                aws_access_key_id=params.get("aws_access_key_id")
                or settings.aws_access_key_id,
                aws_secret_access_key=params.get("aws_secret_access_key")
                or settings.aws_secret_access_key,
                region_name=params.get("region_name") or settings.s3_region_name,
                max_image_px=settings.analysis_max_image_px,
            )

        elif provider == "google_dai":
            from app.services.analysis.google_dai import GoogleDAIAnalysisBackend

            return GoogleDAIAnalysisBackend(
                processor_id=params.get("processor_id")
                or settings.google_dai_processor_id
                or "",
                credentials_path=params.get("credentials_path")
                or settings.google_application_credentials,
                max_image_px=settings.analysis_max_image_px,
            )

        elif provider == "claude":
            from app.services.analysis.claude_vision import ClaudeVisionAnalysisBackend

            return ClaudeVisionAnalysisBackend(
                api_key=params.get("api_key") or settings.anthropic_api_key,
                bedrock_region=params.get("bedrock_region") or settings.bedrock_region,
                model=params.get("model"),
                max_image_px=settings.analysis_max_image_px,
            )

        else:
            raise ValueError(
                f"Unknown analysis provider: {provider!r}. "
                f"Valid options: {', '.join(_VALID_PROVIDERS)}"
            )

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance. Used for test isolation."""
        cls._instance = None
