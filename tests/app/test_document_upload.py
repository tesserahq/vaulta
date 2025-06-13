import pytest
from fastapi import UploadFile
from io import BytesIO
from app.services.document_upload import upload_document
from app.services.document import DocumentService
from app.storage.base import StorageBackend
from app.constants.document import DocumentState


@pytest.fixture
def document_service(db):
    """Create a document service instance for testing."""
    return DocumentService(db)


class MockStorageBackend(StorageBackend):
    """Mock storage backend for testing."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.saved_files: dict[str, UploadFile] = {}
        self.urls: dict[str, str] = {}

    async def save(self, document_id: str, file: UploadFile) -> str:
        """Mock saving a file."""
        if self.should_fail:
            raise Exception("Mock storage failure")
        self.saved_files[document_id] = file
        return document_id

    async def get_url(self, document_id: str) -> str:
        """Mock getting a file URL."""
        return f"/download/{document_id}"

    async def delete(self, filename: str) -> bool:
        """Mock deleting a file."""
        if filename in self.saved_files:
            del self.saved_files[filename]
            return True
        return False

    def verify_token(self, token: str, max_age: int = 3600) -> str:
        """Mock token verification."""
        return token


@pytest.fixture
def mock_storage():
    """Create a mock storage backend."""
    return MockStorageBackend()


@pytest.fixture
def failing_storage():
    """Create a mock storage backend that fails."""
    return MockStorageBackend(should_fail=True)


@pytest.fixture
def test_file():
    """Create a test file for uploading."""
    content = b"Test file content"
    file = UploadFile(
        filename="test.txt",
        file=BytesIO(content),
    )
    file.headers = {"content-type": "text/plain"}
    return file


@pytest.fixture
def test_labels():
    """Create test labels for document upload."""
    return {
        "type": "test",
        "status": "draft",
    }


@pytest.mark.asyncio
async def test_successful_upload(test_file, setup_user, document_service, mock_storage):
    """Test successful file upload."""
    response = await upload_document(
        file=test_file,
        user_id=setup_user.id,
        document_service=document_service,
        storage=mock_storage,
    )

    # Verify response
    assert response.document_id is not None
    assert response.url.startswith("/download/")
    assert response.name == "test.txt"
    assert response.filename == "test.txt"
    assert response.mime_type == "text/plain"
    assert response.size > 0
    assert response.state == DocumentState.COMPLETED.value
    assert response.state_message == "File upload completed successfully"

    # Verify document in database
    document = document_service.get_document(response.document_id)
    assert document is not None
    assert document.name == "test.txt"
    assert document.state == DocumentState.COMPLETED.value


@pytest.mark.asyncio
async def test_upload_with_custom_name_and_labels(
    test_file, setup_user, document_service, mock_storage, test_labels
):
    """Test file upload with custom name and labels."""
    custom_name = "Custom Document Name"
    response = await upload_document(
        file=test_file,
        user_id=setup_user.id,
        document_service=document_service,
        storage=mock_storage,
        name=custom_name,
        labels=test_labels,
    )

    # Verify response
    assert response.name == custom_name
    assert len(response.labels) == 2
    assert response.labels["type"] == "test"
    assert response.labels["status"] == "draft"

    # Verify document in database
    document = document_service.get_document(response.document_id)
    assert document.name == custom_name
    assert len(document.labels) == 2


@pytest.mark.asyncio
async def test_upload_failure(test_file, setup_user, document_service, failing_storage):
    """Test file upload failure handling."""
    with pytest.raises(Exception) as exc_info:
        await upload_document(
            file=test_file,
            user_id=setup_user.id,
            document_service=document_service,
            storage=failing_storage,
        )

    assert str(exc_info.value) == "Mock storage failure"

    # Verify document state is updated to failed
    documents = document_service.get_user_documents(setup_user.id)
    assert len(documents) == 1
    assert documents[0].state == DocumentState.FAILED.value
    assert "Upload failed" in documents[0].state_message


@pytest.mark.asyncio
async def test_upload_state_transitions(
    test_file, setup_user, document_service, mock_storage
):
    """Test document state transitions during upload."""
    response = await upload_document(
        file=test_file,
        user_id=setup_user.id,
        document_service=document_service,
        storage=mock_storage,
    )

    # Verify final state
    document = document_service.get_document(response.document_id)
    assert document.state == DocumentState.COMPLETED.value

    # Verify state history (we can't directly test intermediate states,
    # but we can verify the final state is correct)
    assert document.state_message == "File upload completed successfully"


@pytest.mark.asyncio
async def test_file_metadata_handling(
    test_file, setup_user, document_service, mock_storage
):
    """Test file metadata handling during upload."""
    response = await upload_document(
        file=test_file,
        user_id=setup_user.id,
        document_service=document_service,
        storage=mock_storage,
    )

    # Verify file metadata
    assert response.filename == "test.txt"
    assert response.mime_type == "text/plain"
    assert response.size > 0
    assert response.human_readable_size is not None

    # Verify document in database
    document = document_service.get_document(response.document_id)
    assert document.filename == "test.txt"
    assert document.mime_type == "text/plain"
    assert document.size > 0
