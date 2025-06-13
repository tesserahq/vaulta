from pydantic import BaseModel
from typing import List
from enum import Enum


class ValidationStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class ValidationStep(BaseModel):
    """Represents a single validation step in the system setup process."""

    name: str
    status: ValidationStatus
    message: str


class SystemSetupResponse(BaseModel):
    """Response model for system setup operations."""

    success: bool
    message: str
    details: List[ValidationStep]
