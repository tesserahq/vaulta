import logging

from sqlalchemy.orm import Session

from app.repositories.analysis_config_repository import AnalysisConfigRepository
from app.schemas.analysis_config import (
    AnalysisConfigCreate,
    AnalysisConfigResponse,
)


class CreateAnalysisConfigCommand:
    def __init__(self, db: Session):
        self.db = db
        self.analysis_config_repository = AnalysisConfigRepository(db)
        self.logger = logging.getLogger(__name__)

    def execute(self, data: AnalysisConfigCreate) -> AnalysisConfigResponse:
        try:
            record = self.analysis_config_repository.create(data)
            return AnalysisConfigResponse.model_validate(record)
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create analysis config: {str(e)}")
