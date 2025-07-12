from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from app.constants.asset import AssetState


class AssetBase(BaseModel):
    """Base file model containing common file attributes."""

    name: str
    """Human readable name for the file."""
    filename: str
    """Original filename."""
    mime_type: str
    """File type (e.g., application/pdf, image/jpeg)."""
    size: int
    """File size in bytes."""
    labels: Dict[str, Any] = Field(default_factory=dict)
    """Dictionary of labels."""
    state: str
    state_message: Optional[str] = None

    @field_validator("state")
    @classmethod
    def validate_state(cls, v):
        valid_states = {state.value for state in AssetState}
        if v.lower() not in valid_states:
            raise ValueError(
                f'Invalid state. Must be one of: {", ".join(valid_states)}'
            )
        return v.lower()


class AssetCreate(AssetBase):
    """Schema for creating a new asset."""

    pass


class AssetUpdate(BaseModel):
    """Schema for updating an existing file. All fields are optional."""

    name: Optional[str] = None
    """Updated file name."""
    labels: Optional[Dict[str, Any]] = None
    """Updated file labels."""
    state: Optional[str] = None
    state_message: Optional[str] = None

    @field_validator("state")
    @classmethod
    def validate_state(cls, v):
        if v is not None:
            valid_states = {state.value for state in AssetState}
            if v.lower() not in valid_states:
                raise ValueError(
                    f'Invalid state. Must be one of: {", ".join(valid_states)}'
                )
            return v.lower()
        return v


class AssetInDB(AssetBase):
    """Schema representing a file as stored in the database."""

    id: UUID
    """Unique identifier for the file."""
    user_id: UUID
    """ID of the user who owns the file."""
    created_at: datetime
    """Timestamp when the file was created."""
    updated_at: datetime
    """Timestamp when the file was last updated."""

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class Asset(AssetInDB):
    """Schema for asset data returned in API responses."""

    human_readable_size: str
    """File size in a human-readable format (e.g., '1.5 MB')."""

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class AssetUploadResponse(BaseModel):
    """Schema for file upload response."""

    asset_id: UUID
    """Unique identifier for the uploaded file."""
    url: str
    """URL for accessing the uploaded file."""
    serve_url: str
    """URL for serving the file publicly via token."""
    name: str
    """Human readable name for the file."""
    filename: str
    """Original filename."""
    mime_type: str
    """File type (e.g., application/pdf, image/jpeg)."""
    size: int
    """File size in bytes."""
    human_readable_size: str
    """File size in a human-readable format (e.g., '1.5 MB')."""
    labels: Dict[str, Any]
    """Dictionary of labels."""
    state: str
    """Current state of the file."""
    state_message: str
    """Message describing the current state."""

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class AssetSearchQuery(BaseModel):
    """Schema for file search queries."""

    user_id: Optional[UUID] = None
    """Optional user ID to filter files by owner."""
    labels: Optional[Dict[str, Any]] = None
    """Optional dictionary of labels to filter by."""
    state: Optional[str] = None
    """Optional state to filter by."""
    skip: int = 0
    """Number of records to skip (for pagination)."""
    limit: int = 100
    """Maximum number of records to return."""

    @field_validator("state")
    @classmethod
    def validate_state(cls, v):
        if v is not None:
            valid_states = {state.value for state in AssetState}
            if v.lower() not in valid_states:
                raise ValueError(
                    f'Invalid state. Must be one of: {", ".join(valid_states)}'
                )
            return v.lower()
        return v
