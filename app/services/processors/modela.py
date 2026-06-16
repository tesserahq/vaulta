import logging
from typing import Any

from app.services.processors.base import AssetProcessor, ProcessorContext

logger = logging.getLogger(__name__)


# TODO: We need to improve this timeout, it's too long and we should have a better way to handle this.
MODELA_TIMEOUT = 20


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
    async def process(
        self,
        file_bytes: bytes,
        content_type: str,
        asset_url: str,
        ctx: ProcessorContext,
    ) -> dict[str, Any]:
        try:
            from tessera_sdk.clients.modela.client import ModelaClient

            token = _get_delegated_token(ctx)
            response = ModelaClient(api_token=token, timeout=MODELA_TIMEOUT).scan_file(
                file_url=asset_url,
                mime_type=content_type,
                project_id=ctx.project_id,
            )
            return {"extracted_data": response.data}
        except Exception:
            logger.exception("modela analysis failed")
            return {}


class ModelaSummarizationProcessor(AssetProcessor):
    async def process(
        self,
        file_bytes: bytes,
        content_type: str,
        asset_url: str,
        ctx: ProcessorContext,
    ) -> dict[str, Any]:
        try:
            from tessera_sdk.clients.modela.client import ModelaClient

            token = _get_delegated_token(ctx)
            response = ModelaClient(api_token=token).summarize_file(
                file_url=asset_url,
                mime_type=content_type,
                project_id=ctx.project_id,
            )
            return {
                "summary": {
                    "text": response.summary,
                    "provider": "modela",
                    "model": response.model,
                }
            }
        except Exception:
            logger.exception("modela summarization failed")
            return {}
