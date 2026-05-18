import logging

from sqlalchemy.orm import Session

from app.exceptions.resource_not_found_error import ResourceNotFoundError
from app.models.analysis_config import AnalysisConfig
from app.repositories.analysis_config_repository import AnalysisConfigRepository


class DeleteAnalysisConfigCommand:
    def __init__(self, db: Session):
        self.db = db
        self.analysis_config_repository = AnalysisConfigRepository(db)
        self.logger = logging.getLogger(__name__)

    def execute(self, record: AnalysisConfig) -> None:
        try:
            deleted = self.analysis_config_repository.delete(record.id)
            if not deleted:
                raise ResourceNotFoundError("AnalysisConfig not found")
        except (ValueError, ResourceNotFoundError):
            raise
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to delete analysis config: {str(e)}")
