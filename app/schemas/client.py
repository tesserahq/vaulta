from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class ClientBase(BaseModel):
    """Base client model containing common client attributes."""

    id: Optional[UUID] = None
    """Unique identifier for the client. Defaults to None."""

    name: str
    """Client name. Required field."""

    client_id: str
    """Unique client identifier (slug). Required field."""

    secret_generated_at: Optional[datetime] = None
    """Timestamp when the client secret was last generated."""


class ClientCreate(ClientBase):
    """Schema for creating a new client. Inherits all fields from ClientBase."""

    pass


class ClientUpdate(BaseModel):
    """Schema for updating an existing client. All fields are optional."""

    name: Optional[str] = None
    """Updated client name."""

    client_id: Optional[str] = None
    """Updated client identifier."""

    secret_generated_at: Optional[datetime] = None
    """Updated secret generation timestamp."""


class ClientInDB(ClientBase):
    """Schema representing a client as stored in the database. Includes database-specific fields."""

    id: UUID
    """Unique identifier for the client in the database."""

    created_at: datetime
    """Timestamp when the client record was created."""

    updated_at: datetime
    """Timestamp when the client record was last updated."""

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class Client(ClientInDB):
    """Schema for client data returned in API responses. Inherits all fields from ClientInDB."""

    pass


class ClientWithSecret(ClientInDB):
    """Schema for client data returned when creating a new client, includes the derived secret."""

    secret: str
    """The derived secret for this client."""
