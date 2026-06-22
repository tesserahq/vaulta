from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi_pagination import Page, Params, paginate as paginate_sequence
from fastapi_pagination.ext.sqlalchemy import paginate

from app.auth.rbac import build_rbac_dependencies
from app.commands.analysis_configs.create_analysis_config_command import (
    CreateAnalysisConfigCommand,
)
from app.commands.analysis_configs.delete_analysis_config_command import (
    DeleteAnalysisConfigCommand,
)
from app.commands.analysis_configs.update_analysis_config_command import (
    UpdateAnalysisConfigCommand,
)
from app.db import get_db
from app.models.analysis_config import AnalysisConfig as AnalysisConfigModel
from app.models.user import User
from app.providers import ANALYSIS_PROVIDER_LABELS, AnalysisProvider
from app.routers.utils.dependencies import get_analysis_config_by_id
from app.schemas.analysis_config import (
    AnalysisConfigCreate,
    AnalysisConfigResponse,
    AnalysisConfigUpdate,
    AnalysisProviderResponse,
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/analysis-configs", tags=["analysis-configs"])


async def infer_domain(request: Request) -> Optional[str]:
    return "*"


RESOURCE_ANALYSIS_CONFIG = "analysis_config"
rbac = build_rbac_dependencies(
    resource=RESOURCE_ANALYSIS_CONFIG,
    domain_resolver=infer_domain,
)


@router.get("", response_model=Page[AnalysisConfigResponse])
def list_analysis_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    params: Params = Depends(),
    _authorized: bool = Depends(rbac["read"]),
) -> Page[AnalysisConfigResponse]:
    """Get a paginated list of analysis configs."""
    return paginate(db, select(AnalysisConfigModel), params=params)


@router.get("/providers", response_model=Page[AnalysisProviderResponse])
def list_analysis_providers(
    current_user: User = Depends(get_current_user),
    params: Params = Depends(),
    _authorized: bool = Depends(rbac["read"]),
) -> Page[AnalysisProviderResponse]:
    """List available analysis providers."""
    providers = [
        AnalysisProviderResponse(
            id=provider.value, label=ANALYSIS_PROVIDER_LABELS[provider]
        )
        for provider in AnalysisProvider
    ]
    return paginate_sequence(providers, params=params)


@router.get("/{config_id}", response_model=AnalysisConfigResponse)
def get_analysis_config(
    config: AnalysisConfigModel = Depends(get_analysis_config_by_id),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get a specific analysis config by ID."""
    return config


@router.post("", response_model=AnalysisConfigResponse, status_code=201)
def create_analysis_config(
    data: AnalysisConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Create a new analysis config."""
    return CreateAnalysisConfigCommand(db).execute(data)


@router.patch("/{config_id}", response_model=AnalysisConfigResponse)
def update_analysis_config(
    data: AnalysisConfigUpdate,
    config: AnalysisConfigModel = Depends(get_analysis_config_by_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["update"]),
):
    """Update an existing analysis config."""
    try:
        return UpdateAnalysisConfigCommand(db).execute(config, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{config_id}", status_code=204)
def delete_analysis_config(
    config: AnalysisConfigModel = Depends(get_analysis_config_by_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Delete an analysis config."""
    try:
        DeleteAnalysisConfigCommand(db).execute(config)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return Response(status_code=204)
