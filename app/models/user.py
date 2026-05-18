from sqlalchemy.orm import relationship
from sqlalchemy import Index, text
from tessera_sdk.domain.models import UserMixin

from app.models.mixins import TimestampMixin
from app.db import Base


class User(UserMixin, Base, TimestampMixin):
    """User model for the application.
    This model represents a user in the system and includes fields for
    personal information, authentication, and relationships with other models.
    """

    __tablename__ = "users"

    __table_args__ = (
        Index(
            "uq_users_external_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
    )

    assets = relationship("Asset", back_populates="user", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        rest = self._build_user_attributes_from_kwargs(kwargs)
        super().__init__(**rest)
