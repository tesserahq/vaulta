import logging

from sqlalchemy.orm import Session

from app.exceptions.resource_not_found_error import ResourceNotFoundError
from app.models.analysis_config import AnalysisConfig
from app.repositories.analysis_config_repository import AnalysisConfigRepository
from app.schemas.analysis_config import (
    AnalysisConfigResponse,
    AnalysisConfigUpdate,
)


class UpdateAnalysisConfigCommand:
    def __init__(self, db: Session):
        self.db = db
        self.analysis_config_repository = AnalysisConfigRepository(db)
        self.logger = logging.getLogger(__name__)

    def execute(
        self, record: AnalysisConfig, data: AnalysisConfigUpdate
    ) -> AnalysisConfigResponse:
        try:
            updated = self.analysis_config_repository.update(record.id, data)
            if not updated:
                raise ResourceNotFoundError("AnalysisConfig not found")
            return AnalysisConfigResponse.model_validate(updated)
        except (ValueError, ResourceNotFoundError):
            raise
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to update analysis config: {str(e)}")
