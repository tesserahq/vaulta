from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.analysis_config import AnalysisConfig
from app.schemas.analysis_config import AnalysisConfigCreate, AnalysisConfigUpdate


class AnalysisConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_default(self) -> Optional[AnalysisConfig]:
        return (
            self.db.query(AnalysisConfig)
            .filter(AnalysisConfig.is_default.is_(True))
            .first()
        )

    def get_by_id(self, config_id: UUID) -> Optional[AnalysisConfig]:
        return (
            self.db.query(AnalysisConfig).filter(AnalysisConfig.id == config_id).first()
        )

    def list_all(self) -> List[AnalysisConfig]:
        return self.db.query(AnalysisConfig).all()

    def create(self, data: AnalysisConfigCreate) -> AnalysisConfig:
        if data.is_default:
            self.db.query(AnalysisConfig).filter(
                AnalysisConfig.is_default.is_(True)
            ).update({"is_default": False})

        config = AnalysisConfig(**data.model_dump())
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def update(
        self, config_id: UUID, data: AnalysisConfigUpdate
    ) -> Optional[AnalysisConfig]:
        config = self.get_by_id(config_id)
        if config is None:
            return None

        update_data = data.model_dump(exclude_unset=True)

        if "is_default" in update_data:
            if update_data["is_default"]:
                # Atomically clear the previous default before promoting this one.
                self.db.query(AnalysisConfig).filter(
                    AnalysisConfig.is_default.is_(True),
                    AnalysisConfig.id != config_id,
                ).update({"is_default": False})
            elif config.is_default:
                # Prevent demoting the current default without promoting another,
                # which would leave the system with no default config.
                raise ValueError(
                    "Cannot demote the active default AnalysisConfig. "
                    "Promote another config to default first."
                )

        for key, value in update_data.items():
            setattr(config, key, value)

        self.db.commit()
        self.db.refresh(config)
        return config

    def delete(self, config_id: UUID) -> bool:
        config = self.get_by_id(config_id)
        if config is None:
            return False
        if config.is_default:
            raise ValueError("Cannot delete the active default AnalysisConfig")
        self.db.delete(config)
        self.db.commit()
        return True
