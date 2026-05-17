import uuid

from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db import Base
from app.models.mixins import TimestampMixin


class AnalysisConfig(Base, TimestampMixin):
    __tablename__ = "analysis_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    provider_params = Column(JSONB, nullable=False, default=dict)
