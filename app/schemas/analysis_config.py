from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalysisConfigCreate(BaseModel):
    name: str
    provider: str
    is_default: bool = False
    provider_params: dict[str, Any] = {}


class AnalysisConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    is_default: Optional[bool] = None
    provider_params: Optional[dict[str, Any]] = None


class AnalysisConfigResponse(BaseModel):
    id: UUID
    name: str
    provider: str
    is_default: bool
    provider_params: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisProviderResponse(BaseModel):
    id: str
    label: str
