"""Build the processors an upload asked for from its AnalysisConfig.

Used by the worker, which re-resolves the config by id: processors hold
provider clients and can't be serialized into a task message.
"""

from typing import Any, Optional

from app.models.analysis_config import AnalysisConfig
from app.providers import AnalysisProvider
from app.services.processors.analysis import AnalysisProcessor
from app.services.processors.base import AssetProcessor
from app.services.processors.modela import (
    ModelaAnalysisProcessor,
    ModelaSummarizationProcessor,
)
from app.services.processors.summarization import SummarizationProcessor
from app.services.summarization.claude import ClaudeSummarizationService


def modela_model(params: dict | None) -> str | None:
    """The Modela ModelConfig slug an analysis config asks for, if any.

    Set it as `provider_params.model` (extraction) or
    `summarization_provider_params.model` (summary), e.g. {"model": "will-scan"}.
    """
    model = (params or {}).get("model")
    return model if isinstance(model, str) and model.strip() else None


def build_processors(
    config: Optional[AnalysisConfig],
    extract_data: bool,
    summarize: bool,
    provider: Optional[str] = None,
    provider_params: Optional[dict[str, Any]] = None,
) -> list[AssetProcessor]:
    """`provider` and `provider_params` come from the upload: the provider
    replaces the config's extraction provider, and the params are merged over
    the config's `provider_params`."""
    processors: list[AssetProcessor] = []
    if extract_data:
        extraction_provider = provider or (config.provider if config else None)
        extraction_params = {
            **((config.provider_params or {}) if config else {}),
            **(provider_params or {}),
        }
        if extraction_provider == AnalysisProvider.MODELA:
            processors.append(
                ModelaAnalysisProcessor(model=modela_model(extraction_params))
            )
        else:
            from app.services.analysis.factory import AnalysisFactory

            # No provider and no params: the settings singleton.
            backend = AnalysisFactory.get_backend(
                extraction_provider, extraction_params
            )
            if backend:
                processors.append(AnalysisProcessor(backend))
    if summarize:
        if config and config.summarization_provider == AnalysisProvider.MODELA:
            processors.append(
                ModelaSummarizationProcessor(
                    model=modela_model(config.summarization_provider_params)
                )
            )
        else:
            processors.append(SummarizationProcessor(ClaudeSummarizationService()))
    return processors
