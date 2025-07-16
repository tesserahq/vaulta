from typing import TypeVar, Generic, List, Optional
from pydantic import BaseModel

T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    """Generic response model for wrapping list responses."""

    data: List[T]


class MessageResponse(BaseModel):
    """Generic response model for simple message responses."""

    message: str
    details: Optional[dict] = None
