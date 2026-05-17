from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.repositories.analysis_config_repository import AnalysisConfigRepository
from app.schemas.analysis_config import (
    AnalysisConfigCreate,
    AnalysisConfigResponse,
    AnalysisConfigUpdate,
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/analysis-configs", tags=["analysis-configs"])


@router.get("", response_model=List[AnalysisConfigResponse])
async def list_analysis_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return AnalysisConfigRepository(db).list_all()


@router.get("/{config_id}", response_model=AnalysisConfigResponse)
async def get_analysis_config(
    config_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = AnalysisConfigRepository(db).get_by_id(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="AnalysisConfig not found")
    return config


@router.post("", response_model=AnalysisConfigResponse, status_code=201)
async def create_analysis_config(
    data: AnalysisConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return AnalysisConfigRepository(db).create(data)


@router.patch("/{config_id}", response_model=AnalysisConfigResponse)
async def update_analysis_config(
    config_id: UUID,
    data: AnalysisConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        config = AnalysisConfigRepository(db).update(config_id, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if config is None:
        raise HTTPException(status_code=404, detail="AnalysisConfig not found")
    return config


@router.delete("/{config_id}", status_code=204)
async def delete_analysis_config(
    config_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = AnalysisConfigRepository(db)
    try:
        deleted = repo.delete(config_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="AnalysisConfig not found")
