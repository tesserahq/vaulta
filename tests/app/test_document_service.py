import pytest
from app.services.document import DocumentService
from app.schemas.document import DocumentCreate, DocumentUpdate, DocumentSearchQuery
from app.constants.document import DocumentState


@pytest.fixture
def document_service(db):
    """Create a DocumentService instance for testing."""
    return DocumentService(db)


def test_create_document(document_service, setup_user):
    """Test creating a new document."""
    document_data = DocumentCreate(
        name="Test Document",
        filename="test.pdf",
        mime_type="application/pdf",
        size=1024,
        labels={
            "type": "contract",
            "status": "draft",
        },
        state=DocumentState.PENDING.value,
        state_message="New document created",
    )

    document = document_service.create_document(document_data, setup_user.id)

    assert document.name == document_data.name
    assert document.filename == document_data.filename
    assert document.mime_type == document_data.mime_type
    assert document.size == document_data.size
    assert document.user_id == setup_user.id
    assert document.labels["type"] == "contract"
    assert document.labels["status"] == "draft"
    assert document.state == DocumentState.PENDING.value
    assert document.state_message == "New document created"


def test_get_document(document_service, test_document):
    """Test retrieving a document by ID."""
    retrieved_document = document_service.get_document(test_document.id)

    assert retrieved_document is not None
    assert retrieved_document.id == test_document.id
    assert retrieved_document.name == test_document.name
    assert retrieved_document.state == test_document.state
    assert retrieved_document.state_message == test_document.state_message


def test_get_user_documents(
    document_service,
    test_user,
    test_document,
):
    """Test retrieving all documents for a user."""
    documents = document_service.get_user_documents(test_user.id)

    assert len(documents) == 1
    assert documents[0].user_id == test_user.id
    assert documents[0].name == test_document.name


def test_update_document(document_service, test_document):
    """Test updating a document."""
    update_data = DocumentUpdate(
        name="Updated Document",
        labels={
            "type": "contract",
            "status": "signed",
        },
        state=DocumentState.FAILED.value,
        state_message="Document update failed",
    )

    updated_document = document_service.update_document(test_document.id, update_data)

    assert updated_document.name == "Updated Document"
    assert len(updated_document.labels) == 2
    assert updated_document.labels["status"] == "signed"
    assert updated_document.state == DocumentState.FAILED.value
    assert updated_document.state_message == "Document update failed"


def test_delete_document(document_service, test_document):
    """Test deleting a document."""
    result = document_service.delete_document(test_document.id)

    assert result is True
    assert document_service.get_document(test_document.id) is None


def test_search_documents(
    document_service,
    test_user,
    setup_user,
    test_document,
):
    """Test searching documents with the unified search functionality."""
    # Test search by user_id only
    query = DocumentSearchQuery(user_id=test_user.id)
    results = document_service.search(query)
    assert len(results) == 1  # All three test documents belong to setup_user
    assert results[0].user_id == test_user.id

    # Test search by labels only
    query = DocumentSearchQuery(labels={"category": "test"})
    results = document_service.search(query)
    assert len(results) == 1  # One document is a contract
    assert results[0].labels["category"] == "test"

    # Test search by state only
    query = DocumentSearchQuery(state=DocumentState.PENDING.value)
    results = document_service.search(query)
    assert len(results) == 1
    assert results[0].state == DocumentState.PENDING.value

    # Test search by user_id and labels
    query = DocumentSearchQuery(user_id=test_user.id, labels={"category": "test"})
    results = document_service.search(query)
    assert len(results) == 1
    assert results[0].user_id == test_user.id
    assert results[0].labels["category"] == "test"

    # Test search by user_id, labels, and state
    query = DocumentSearchQuery(
        user_id=test_user.id,
        labels={"category": "test"},
        state=DocumentState.PENDING.value,
    )
    results = document_service.search(query)
    assert len(results) == 1
    assert results[0].user_id == test_user.id
    assert results[0].labels["category"] == "test"
    assert results[0].state == DocumentState.PENDING.value

    # Test pagination
    query = DocumentSearchQuery(user_id=test_user.id, limit=2)
    results = document_service.search(query)
    assert len(results) == 1

    # Test search with no filters (should return all documents)
    query = DocumentSearchQuery()
    results = document_service.search(query)
    assert len(results) == 1  # All three test documents
