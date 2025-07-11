import pytest
from fastapi import UploadFile
from io import BytesIO
from app.services.asset_upload import upload_asset
from app.services.asset_service import AssetService
from app.storage.base import StorageBackend
from app.constants.asset import AssetState


@pytest.fixture
def asset_service(db):
    """Create a asset service instance for testing."""
    return AssetService(db)


class MockStorageBackend(StorageBackend):
    """Mock storage backend for testing."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.saved_assets: dict[str, UploadFile] = {}
        self.urls: dict[str, str] = {}

    async def save(self, asset_id: str, file: UploadFile) -> str:
        """Mock saving a file."""
        if self.should_fail:
            raise Exception("Mock storage failure")
        self.saved_assets[asset_id] = file
        return asset_id

    async def get_url(self, asset_id: str) -> str:
        """Mock getting a file URL."""
        return f"/download/{asset_id}"

    async def delete(self, filename: str) -> bool:
        """Mock deleting a file."""
        if filename in self.saved_assets:
            del self.saved_assets[filename]
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
def test_asset():
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
    """Create test labels for file upload."""
    return {
        "type": "test",
        "status": "draft",
    }


@pytest.mark.asyncio
async def test_successful_upload(test_asset, setup_user, asset_service, mock_storage):
    """Test successful file upload."""
    response = await upload_asset(
        file=test_asset,
        user_id=setup_user.id,
        asset_service=asset_service,
        storage=mock_storage,
    )

    # Verify response
    assert response.asset_id is not None
    assert response.url.startswith("/download/")
    assert response.name == "test.txt"
    assert response.filename == "test.txt"
    assert response.mime_type == "text/plain"
    assert response.size > 0
    assert response.state == AssetState.COMPLETED.value
    assert response.state_message == "File upload completed successfully"

    # Verify file in database
    file = asset_service.get_asset(response.asset_id)
    assert file is not None
    assert file.name == "test.txt"
    assert file.state == AssetState.COMPLETED.value


@pytest.mark.asyncio
async def test_upload_with_custom_name_and_labels(
    test_asset, setup_user, asset_service, mock_storage, test_labels
):
    """Test file upload with custom name and labels."""
    custom_name = "Custom File Name"
    response = await upload_asset(
        file=test_asset,
        user_id=setup_user.id,
        asset_service=asset_service,
        storage=mock_storage,
        name=custom_name,
        labels=test_labels,
    )

    # Verify response
    assert response.name == custom_name
    assert len(response.labels) == 2
    assert response.labels["type"] == "test"
    assert response.labels["status"] == "draft"

    # Verify file in database
    file = asset_service.get_asset(response.asset_id)
    assert file.name == custom_name
    assert len(file.labels) == 2


@pytest.mark.asyncio
async def test_upload_failure(test_asset, setup_user, asset_service, failing_storage):
    """Test file upload failure handling."""
    with pytest.raises(Exception) as exc_info:
        await upload_asset(
            file=test_asset,
            user_id=setup_user.id,
            asset_service=asset_service,
            storage=failing_storage,
        )

    assert str(exc_info.value) == "Mock storage failure"

    # Verify file state is updated to failed
    assets = asset_service.get_user_assets(setup_user.id)
    assert len(assets) == 1
    assert assets[0].state == AssetState.FAILED.value
    assert "Upload failed" in assets[0].state_message


@pytest.mark.asyncio
async def test_upload_state_transitions(
    test_asset, setup_user, asset_service, mock_storage
):
    """Test asset state transitions during upload."""
    response = await upload_asset(
        file=test_asset,
        user_id=setup_user.id,
        asset_service=asset_service,
        storage=mock_storage,
    )

    # Verify final state
    file = asset_service.get_asset(response.asset_id)
    assert file.state == AssetState.COMPLETED.value

    # Verify state history (we can't directly test intermediate states,
    # but we can verify the final state is correct)
    assert file.state_message == "File upload completed successfully"


@pytest.mark.asyncio
async def test_asset_metadata_handling(
    test_asset, setup_user, asset_service, mock_storage
):
    """Test asset metadata handling during upload."""
    response = await upload_asset(
        file=test_asset,
        user_id=setup_user.id,
        asset_service=asset_service,
        storage=mock_storage,
    )

    # Verify file metadata
    assert response.filename == "test.txt"
    assert response.mime_type == "text/plain"
    assert response.size > 0
    assert response.human_readable_size is not None

    # Verify file in database
    file = asset_service.get_asset(response.asset_id)
    assert file.filename == "test.txt"
    assert file.mime_type == "text/plain"
    assert file.size > 0
