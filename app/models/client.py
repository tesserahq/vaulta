from app.models.mixins import TimestampMixin
from sqlalchemy import Column, String, DateTime, Index, text
from sqlalchemy.dialects.postgresql import UUID

import uuid

from app.db import Base


class Client(Base, TimestampMixin):
    """Client model for the application.
    This model represents a client in the system and includes fields for
    client identification and secret management.
    """

    __tablename__ = "clients"

    __table_args__ = (
        Index(
            "uq_clients_client_id",
            "client_id",
            unique=True,
            postgresql_where=text("client_id IS NOT NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    client_id = Column(String, unique=True, nullable=False)
    secret_generated_at = Column(DateTime, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
