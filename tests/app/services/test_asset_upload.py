import pytest
from unittest.mock import patch
from uuid import uuid4
from fastapi import UploadFile
from io import BytesIO
from app.services.asset_upload import ProcessingRequest, upload_asset
from app.services.processors.base import ProcessorContext
from app.repositories.asset_repository import AssetRepository
from app.storage.base import StorageBackend
from app.constants.asset import AssetState


@pytest.fixture
def asset_repository(db):
    """Create an AssetRepository instance for testing."""
    return AssetRepository(db)


class MockStorageBackend(StorageBackend):
    """Mock storage backend for testing."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.saved_assets: dict[str, UploadFile] = {}
        self.urls: dict[str, str] = {}

    def save(self, asset_id: str, file: UploadFile) -> str:
        """Mock saving a file."""
        if self.should_fail:
            raise Exception("Mock storage failure")
        self.saved_assets[asset_id] = file
        return asset_id

    def get_url(self, asset_id: str) -> str:
        """Mock getting a file URL."""
        return f"/download/{asset_id}"

    def read(self, asset_id: str) -> bytes:
        """Mock reading a file."""
        return b"Test file content"

    def delete(self, filename: str) -> bool:
        """Mock deleting a file."""
        if filename in self.saved_assets:
            del self.saved_assets[filename]
            return True
        return False


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


def test_successful_upload(test_asset, setup_user, asset_repository, mock_storage, db):
    """Test successful file upload."""
    response = upload_asset(
        file=test_asset,
        user_id=setup_user.id,
        db=db,
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
    file = asset_repository.get_asset(response.asset_id)
    assert file is not None
    assert file.name == "test.txt"
    assert file.state == AssetState.COMPLETED.value


def test_upload_with_custom_name_and_labels(
    test_asset, setup_user, asset_repository, mock_storage, test_labels, db
):
    """Test file upload with custom name and labels."""
    custom_name = "Custom File Name"
    response = upload_asset(
        file=test_asset,
        user_id=setup_user.id,
        db=db,
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
    file = asset_repository.get_asset(response.asset_id)
    assert file.name == custom_name
    assert len(file.labels) == 2


def test_upload_failure(test_asset, setup_user, asset_repository, failing_storage, db):
    """Test file upload failure handling."""
    with pytest.raises(Exception) as exc_info:
        upload_asset(
            file=test_asset,
            user_id=setup_user.id,
            db=db,
            storage=failing_storage,
        )

    assert str(exc_info.value) == "Mock storage failure"

    # Verify file state is updated to failed
    assets = asset_repository.get_user_assets(setup_user.id)
    assert len(assets) == 1
    assert assets[0].state == AssetState.FAILED.value
    assert "Upload failed" in assets[0].state_message


def test_upload_state_transitions(
    test_asset, setup_user, asset_repository, mock_storage, db
):
    """Test asset state transitions during upload."""
    response = upload_asset(
        file=test_asset,
        user_id=setup_user.id,
        db=db,
        storage=mock_storage,
    )

    # Verify final state
    file = asset_repository.get_asset(response.asset_id)
    assert file.state == AssetState.COMPLETED.value

    # Verify state history (we can't directly test intermediate states,
    # but we can verify the final state is correct)
    assert file.state_message == "File upload completed successfully"


def test_asset_metadata_handling(
    test_asset, setup_user, asset_repository, mock_storage, db
):
    """Test asset metadata handling during upload."""
    response = upload_asset(
        file=test_asset,
        user_id=setup_user.id,
        db=db,
        storage=mock_storage,
    )

    # Verify file metadata
    assert response.filename == "test.txt"
    assert response.mime_type == "text/plain"
    assert response.size > 0
    assert response.human_readable_size is not None

    # Verify file in database
    file = asset_repository.get_asset(response.asset_id)
    assert file.filename == "test.txt"
    assert file.mime_type == "text/plain"
    assert file.size > 0


def _processing(
    user_id,
    extract_data=True,
    summarize=False,
    config_id=None,
    provider=None,
    provider_params=None,
):
    return ProcessingRequest(
        extract_data=extract_data,
        summarize=summarize,
        config_id=config_id,
        provider=provider,
        provider_params=provider_params,
        ctx=ProcessorContext(user_id=user_id, project_id="project-1"),
    )


def test_processing_request_returns_processing_and_queues_task(
    test_asset, setup_user, asset_repository, mock_storage, db
):
    config_id = uuid4()
    with patch("app.tasks.process_asset.process_asset_task.delay") as delay:
        response = upload_asset(
            file=test_asset,
            user_id=setup_user.id,
            db=db,
            storage=mock_storage,
            processing=_processing(
                setup_user.id, extract_data=True, summarize=True, config_id=config_id
            ),
        )

    assert response.state == AssetState.PROCESSING.value
    assert response.extracted_data is None
    assert response.summary is None
    assert asset_repository.get_asset(response.asset_id).state == (
        AssetState.PROCESSING.value
    )
    delay.assert_called_once_with(
        str(response.asset_id),
        True,
        True,
        str(config_id),
        str(setup_user.id),
        "project-1",
        None,
        None,
    )


def test_processing_request_forwards_the_override_to_the_task(
    test_asset, setup_user, mock_storage, db
):
    with patch("app.tasks.process_asset.process_asset_task.delay") as delay:
        response = upload_asset(
            file=test_asset,
            user_id=setup_user.id,
            db=db,
            storage=mock_storage,
            processing=_processing(
                setup_user.id,
                provider="modela",
                provider_params={"model": "will-scan"},
            ),
        )

    delay.assert_called_once_with(
        str(response.asset_id),
        True,
        False,
        None,
        str(setup_user.id),
        "project-1",
        "modela",
        {"model": "will-scan"},
    )


def test_no_processing_requested_completes_without_queueing(
    test_asset, setup_user, mock_storage, db
):
    with patch("app.tasks.process_asset.process_asset_task.delay") as delay:
        response = upload_asset(
            file=test_asset,
            user_id=setup_user.id,
            db=db,
            storage=mock_storage,
            processing=_processing(setup_user.id, extract_data=False),
        )

    assert response.state == AssetState.COMPLETED.value
    delay.assert_not_called()


def test_queue_failure_keeps_upload_and_marks_processing_failed(
    test_asset, setup_user, asset_repository, mock_storage, db
):
    with patch(
        "app.tasks.process_asset.process_asset_task.delay",
        side_effect=ConnectionError("redis down"),
    ):
        response = upload_asset(
            file=test_asset,
            user_id=setup_user.id,
            db=db,
            storage=mock_storage,
            processing=_processing(setup_user.id),
        )

    assert response.state == AssetState.PROCESSING_FAILED.value
    assert response.state_message == "Processing could not be queued"
    assert "redis down" not in response.state_message
    stored = asset_repository.get_asset(response.asset_id)
    assert stored.state == AssetState.PROCESSING_FAILED.value
    assert response.asset_id in mock_storage.saved_assets
