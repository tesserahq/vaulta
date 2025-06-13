from app.models.mixins import TimestampMixin
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db import Base


class Document(Base, TimestampMixin):
    """Document model for storing file information.
    This model represents a document in the system and includes fields for
    file metadata, storage information, and relationships with other models.
    """

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)  # Human readable name
    filename = Column(String, nullable=False)  # Original filename
    mime_type = Column(String, nullable=False)  # File type
    size = Column(Integer, nullable=False)  # File size in bytes
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )  # Owner of the document
    labels = Column(
        JSONB, default=list, nullable=False
    )  # Array of key-value pairs for document labels
    state = Column(String, nullable=False)  # Document state
    state_message = Column(
        String, nullable=True
    )  # Message describing the current state

    # Relationships
    user = relationship("User", back_populates="documents")

    @property
    def human_readable_size(self) -> str:
        """Return the file size in a human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if self.size < 1024.0:
                return f"{self.size:.1f} {unit}"
            self.size /= 1024.0
        return f"{self.size:.1f} PB"
