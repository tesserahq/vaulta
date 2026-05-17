from abc import ABC, abstractmethod
from pydantic import BaseModel


class FieldValue(BaseModel):
    value: str | None
    confidence: float


class AnalysisResult(BaseModel):
    document_type: str  # "passport" | "drivers_license" | "national_id" | "social_security_card" | "unknown"
    document_type_confidence: float
    fields: dict[str, FieldValue]
    partial: bool
    provider: str


# Expected fields per document type — shared across all providers to ensure consistent partial detection.
EXPECTED_FIELDS_BY_TYPE: dict[str, set[str]] = {
    "passport": {
        "given_names",
        "surname",
        "date_of_birth",
        "expiration_date",
        "document_number",
    },
    "drivers_license": {
        "given_names",
        "surname",
        "date_of_birth",
        "expiration_date",
        "document_number",
    },
    "national_id": {"given_names", "surname", "date_of_birth", "document_number"},
    "social_security_card": {"ssn"},
    "unknown": set(),
}


def is_partial(doc_type: str, fields: dict) -> bool:
    """True when doc_type is unknown (provider couldn't classify) or any expected field is absent."""
    if doc_type == "unknown":
        return True
    expected = EXPECTED_FIELDS_BY_TYPE.get(doc_type, set())
    return bool(expected) and any(f not in fields for f in expected)


class DocumentAnalysisBackend(ABC):
    @abstractmethod
    async def analyze(self, file_bytes: bytes, content_type: str) -> AnalysisResult:
        pass
