import logging
from typing import Any

from app.services.processors.base import AssetProcessor, ProcessorContext

logger = logging.getLogger(__name__)


def _scan_timeout() -> int:
    from app.config import get_settings

    return get_settings().modela_scan_timeout


def _summary_timeout() -> int:
    from app.config import get_settings

    return get_settings().modela_summary_timeout


def _model_kwargs(model: str | None) -> dict[str, str]:
    """Only send `model` when one is configured, so Modela keeps its default otherwise."""
    return {"model": model} if model else {}


def _get_delegated_token(ctx: ProcessorContext) -> str:
    from app.config import get_settings
    from tessera_sdk.clients.identies.client import IdentiesClient
    from tessera_sdk.infra.m2m_token import M2MTokenClient

    settings = get_settings()
    m2m_token = M2MTokenClient().get_token_sync().access_token
    identies = IdentiesClient(api_token=m2m_token)
    response = identies.exchange_token(
        user_id=str(ctx.user_id),
        requested_audience=settings.modela_audience,
        requested_scope=settings.modela_scope,
    )
    return response.access_token


class ModelaAnalysisProcessor(AssetProcessor):
    """Runs Modela's /scan/file.

    `model` is a Modela ModelConfig slug (e.g. "will-scan"); its output_schema
    decides the shape of `extracted_data`. Without it Modela uses its default
    scan config.
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def process(
        self,
        file_bytes: bytes,
        content_type: str,
        asset_url: str,
        ctx: ProcessorContext,
    ) -> dict[str, Any]:
        try:
            from tessera_sdk.clients.modela.client import ModelaClient

            token = _get_delegated_token(ctx)
            response = ModelaClient(api_token=token, timeout=_scan_timeout()).scan_file(
                file_url=asset_url,
                mime_type=content_type,
                project_id=ctx.project_id,
                **_model_kwargs(self.model),
            )
            return {"extracted_data": response.data}
        except Exception:
            logger.exception("modela analysis failed", extra={"model": self.model})
            return {}


class ModelaSummarizationProcessor(AssetProcessor):
    """Runs Modela's /summarize/file, optionally with a specific ModelConfig slug."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def process(
        self,
        file_bytes: bytes,
        content_type: str,
        asset_url: str,
        ctx: ProcessorContext,
    ) -> dict[str, Any]:
        try:
            from tessera_sdk.clients.modela.client import ModelaClient

            token = _get_delegated_token(ctx)
            response = ModelaClient(
                api_token=token, timeout=_summary_timeout()
            ).summarize_file(
                file_url=asset_url,
                mime_type=content_type,
                project_id=ctx.project_id,
                **_model_kwargs(self.model),
            )
            return {
                "summary": {
                    "text": response.summary,
                    "provider": "modela",
                    "model": response.model,
                }
            }
        except Exception:
            logger.exception("modela summarization failed", extra={"model": self.model})
            return {}
