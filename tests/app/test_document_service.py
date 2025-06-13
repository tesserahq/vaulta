import pytest
from app.services.document import DocumentService
from app.schemas.document import DocumentCreate, DocumentUpdate, Label
from app.constants.document import DocumentState


@pytest.fixture
def document_service(db):
    """Create a DocumentService instance for testing."""
    return DocumentService(db)


@pytest.fixture
def test_document(db, setup_user, document_service):
    """Create a test document."""
    document_data = DocumentCreate(
        name="Test Document",
        filename="test.pdf",
        mime_type="application/pdf",
        size=1024,
        labels=[
            Label(key="type", value="contract"),
            Label(key="status", value="draft"),
        ],
        state=DocumentState.COMPLETED.value,
        state_message="Document created for testing",
    )
    return document_service.create_document(document_data, setup_user.id)


@pytest.fixture
def test_document_with_report(db, setup_user, document_service):
    """Create a test document for monthly report."""
    document_data = DocumentCreate(
        name="Monthly Report",
        filename="report.pdf",
        mime_type="application/pdf",
        size=2048,
        labels=[
            Label(key="type", value="report"),
            Label(key="status", value="review"),
        ],
        state=DocumentState.COMPLETED.value,
        state_message="Monthly report document",
    )
    return document_service.create_document(document_data, setup_user.id)


@pytest.fixture
def test_document_with_signed_contract(db, setup_user, document_service):
    """Create a test document for signed contract."""
    document_data = DocumentCreate(
        name="Signed Contract",
        filename="contract.pdf",
        mime_type="application/pdf",
        size=3072,
        labels=[
            Label(key="type", value="contract"),
            Label(key="status", value="signed"),
        ],
        state=DocumentState.COMPLETED.value,
        state_message="Signed contract document",
    )
    return document_service.create_document(document_data, setup_user.id)


@pytest.fixture
def test_document_with_many_labels(db, setup_user, document_service):
    """Create a test document with multiple labels for complex searches."""
    document_data = DocumentCreate(
        name="Complex Document",
        filename="complex.pdf",
        mime_type="application/pdf",
        size=4096,
        labels=[
            Label(key="type", value="contract"),
            Label(key="priority", value="high"),
            Label(key="department", value="legal"),
            Label(key="year", value="2024"),
        ],
        state=DocumentState.COMPLETED.value,
        state_message="Complex document with multiple labels",
    )
    return document_service.create_document(document_data, setup_user.id)


def test_create_document(document_service, setup_user):
    """Test creating a new document."""
    document_data = DocumentCreate(
        name="Test Document",
        filename="test.pdf",
        mime_type="application/pdf",
        size=1024,
        labels=[
            Label(key="type", value="contract"),
            Label(key="status", value="draft"),
        ],
        state=DocumentState.PENDING.value,
        state_message="New document created",
    )

    document = document_service.create_document(document_data, setup_user.id)

    assert document.name == document_data.name
    assert document.filename == document_data.filename
    assert document.mime_type == document_data.mime_type
    assert document.size == document_data.size
    assert document.user_id == setup_user.id
    assert len(document.labels) == 2
    assert document.labels[0]["key"] == "type"
    assert document.labels[0]["value"] == "contract"
    assert document.labels[1]["key"] == "status"
    assert document.labels[1]["value"] == "draft"
    assert document.state == DocumentState.PENDING.value
    assert document.state_message == "New document created"


def test_get_document(document_service, test_document):
    """Test retrieving a document by ID."""
    retrieved_document = document_service.get_document(test_document.id)

    assert retrieved_document is not None
    assert retrieved_document.id == test_document.id
    assert retrieved_document.name == test_document.name
    assert retrieved_document.state == DocumentState.COMPLETED.value
    assert retrieved_document.state_message == "Document created for testing"


def test_get_user_documents(
    document_service,
    setup_user,
    test_document,
    test_document_with_report,
    test_document_with_signed_contract,
):
    """Test retrieving all documents for a user."""
    documents = document_service.get_user_documents(setup_user.id)

    assert len(documents) == 3
    assert all(doc.user_id == setup_user.id for doc in documents)
    assert any(doc.name == "Test Document" for doc in documents)
    assert any(doc.name == "Monthly Report" for doc in documents)
    assert any(doc.name == "Signed Contract" for doc in documents)


def test_update_document(document_service, test_document):
    """Test updating a document."""
    update_data = DocumentUpdate(
        name="Updated Document",
        labels=[
            Label(key="type", value="contract"),
            Label(key="status", value="signed"),
        ],
        state=DocumentState.FAILED.value,
        state_message="Document update failed",
    )

    updated_document = document_service.update_document(test_document.id, update_data)

    assert updated_document.name == "Updated Document"
    assert len(updated_document.labels) == 2
    assert updated_document.labels[1]["value"] == "signed"
    assert updated_document.state == DocumentState.FAILED.value
    assert updated_document.state_message == "Document update failed"


def test_delete_document(document_service, test_document):
    """Test deleting a document."""
    result = document_service.delete_document(test_document.id)

    assert result is True
    assert document_service.get_document(test_document.id) is None


def test_search_by_labels(
    document_service,
    setup_user,
    test_document,
    test_document_with_report,
    test_document_with_signed_contract,
):
    """Test searching documents by labels."""
    # Search for documents with type=contract
    results = document_service.search_by_labels(
        setup_user.id, [{"key": "type", "value": "contract"}]
    )

    assert len(results) == 2  # Two documents are contracts
    assert all(doc.labels[0]["value"] == "contract" for doc in results)

    # Search for documents with status=draft
    results = document_service.search_by_labels(
        setup_user.id, [{"key": "status", "value": "draft"}]
    )

    assert len(results) == 1
    assert results[0].name == "Test Document"


def test_search_by_label_values(
    document_service, setup_user, test_document, test_document_with_report
):
    """Test searching documents by label values."""
    # Search for documents with status=draft OR status=review
    results = document_service.search_by_label_values(
        setup_user.id, "status", ["draft", "review"]
    )

    assert len(results) == 2
    statuses = [doc.labels[1]["value"] for doc in results]
    assert "draft" in statuses
    assert "review" in statuses


def test_search_documents(
    document_service,
    setup_user,
    test_document,
    test_document_with_report,
    test_document_with_signed_contract,
):
    """Test searching documents with filters."""
    # Search by name
    results = document_service.search(setup_user.id, {"name": "Test Document"})
    assert len(results) == 1
    assert results[0].name == "Test Document"

    # Search by mime type
    results = document_service.search(setup_user.id, {"mime_type": "application/pdf"})
    assert len(results) == 3

    # Search with multiple filters
    results = document_service.search(
        setup_user.id,
        {
            "name": {"operator": "ilike", "value": "%Contract%"},
            "size": {"operator": ">", "value": 1500},
        },
    )
    assert len(results) == 1
    assert results[0].name == "Signed Contract"


def test_complex_label_search(
    document_service, setup_user, test_document_with_many_labels
):
    """Test searching documents with complex label combinations."""
    # Search for high priority contracts
    results = document_service.search_by_labels(
        setup_user.id,
        [{"key": "type", "value": "contract"}, {"key": "priority", "value": "high"}],
    )

    assert len(results) == 1
    assert results[0].name == "Complex Document"

    # Search for legal department documents from 2024
    results = document_service.search_by_labels(
        setup_user.id,
        [{"key": "department", "value": "legal"}, {"key": "year", "value": "2024"}],
    )

    assert len(results) == 1
    assert results[0].name == "Complex Document"


def test_search_by_state(document_service, setup_user, test_document):
    """Test searching documents by state."""
    results = document_service.search(
        setup_user.id, {"state": DocumentState.COMPLETED.value}
    )

    assert len(results) == 1
    assert results[0].id == test_document.id
    assert results[0].state == DocumentState.COMPLETED.value
