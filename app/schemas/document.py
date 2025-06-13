from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.constants.document import DocumentState


class Label(BaseModel):
    """Schema for document labels."""

    key: str
    value: str


class DocumentBase(BaseModel):
    """Base document model containing common document attributes."""

    name: str
    """Human readable name for the document."""
    filename: str
    """Original filename."""
    mime_type: str
    """File type (e.g., application/pdf, image/jpeg)."""
    size: int
    """File size in bytes."""
    labels: List[Label] = Field(default_factory=list)
    """Array of key-value pairs for document labels."""
    state: str
    state_message: Optional[str] = None

    @field_validator("state")
    @classmethod
    def validate_state(cls, v):
        valid_states = {state.value for state in DocumentState}
        if v.lower() not in valid_states:
            raise ValueError(
                f'Invalid state. Must be one of: {", ".join(valid_states)}'
            )
        return v.lower()


class DocumentCreate(DocumentBase):
    """Schema for creating a new document."""

    pass


class DocumentUpdate(BaseModel):
    """Schema for updating an existing document. All fields are optional."""

    name: Optional[str] = None
    """Updated document name."""
    labels: Optional[List[Label]] = None
    """Updated document labels."""
    state: Optional[str] = None
    state_message: Optional[str] = None

    @field_validator("state")
    @classmethod
    def validate_state(cls, v):
        if v is not None:
            valid_states = {state.value for state in DocumentState}
            if v.lower() not in valid_states:
                raise ValueError(
                    f'Invalid state. Must be one of: {", ".join(valid_states)}'
                )
            return v.lower()
        return v


class DocumentInDB(DocumentBase):
    """Schema representing a document as stored in the database."""

    id: UUID
    """Unique identifier for the document."""
    user_id: UUID
    """ID of the user who owns the document."""
    created_at: datetime
    """Timestamp when the document was created."""
    updated_at: datetime
    """Timestamp when the document was last updated."""

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class Document(DocumentInDB):
    """Schema for document data returned in API responses."""

    human_readable_size: str
    """File size in a human-readable format (e.g., '1.5 MB')."""

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """Schema for document upload response."""

    document_id: UUID
    """Unique identifier for the uploaded document."""
    url: str
    """URL for accessing the uploaded file."""
    name: str
    """Human readable name for the document."""
    filename: str
    """Original filename."""
    mime_type: str
    """File type (e.g., application/pdf, image/jpeg)."""
    size: int
    """File size in bytes."""
    human_readable_size: str
    """File size in a human-readable format (e.g., '1.5 MB')."""
    labels: List[Label]
    """Array of key-value pairs for document labels."""
    state: str
    """Current state of the document."""
    state_message: str
    """Message describing the current state."""

    class Config:
        """Pydantic model configuration."""

        from_attributes = True
