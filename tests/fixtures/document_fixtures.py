import pytest
from app.models.document import Document

from app.constants.document import DocumentState


@pytest.fixture(scope="function")
def test_document(db, test_user):
    """Create a test document for use in tests."""
    document_data = {
        "name": "Test Document",
        "filename": "test_document.pdf",
        "mime_type": "application/pdf",
        "size": 1024,  # 1KB
        "user_id": test_user.id,
        "labels": {"category": "test", "type": "pdf"},
        "state": DocumentState.PENDING.value,
        "state_message": "Document processed successfully",
    }

    document = Document(**document_data)
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


@pytest.fixture(scope="function")
def setup_document(db, setup_user):
    """Create a test document for use in tests."""
    document_data = {
        "name": "Setup Document",
        "filename": "setup_document.pdf",
        "mime_type": "application/pdf",
        "size": 2048,  # 2KB
        "user_id": setup_user.id,
        "labels": {"category": "setup", "type": "pdf"},
        "state": DocumentState.PENDING.value,
        "state_message": "Document processed successfully",
    }

    document = Document(**document_data)
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


@pytest.fixture(scope="function")
def setup_another_document(db, setup_another_user):
    """Create another test document for use in tests."""
    document_data = {
        "name": "Another Document",
        "filename": "another_document.pdf",
        "mime_type": "application/pdf",
        "size": 3072,  # 3KB
        "user_id": setup_another_user.id,
        "labels": {"category": "another", "type": "pdf"},
        "state": DocumentState.PENDING.value,
        "state_message": "Document processed successfully",
    }

    document = Document(**document_data)
    db.add(document)
    db.commit()
    db.refresh(document)

    return document
