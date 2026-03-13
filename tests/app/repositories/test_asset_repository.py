import pytest
from app.repositories.asset_repository import AssetRepository
from app.schemas.asset import AssetCreate, AssetUpdate, AssetSearchQuery
from app.constants.asset import AssetState


@pytest.fixture
def asset_repository(db):
    """Create an AssetRepository instance for testing."""
    return AssetRepository(db)


def test_create_asset(asset_repository, setup_user):
    """Test creating a new asset."""
    asset_data = AssetCreate(
        name="Test File",
        filename="test.pdf",
        mime_type="application/pdf",
        size=1024,
        labels={
            "type": "contract",
            "status": "draft",
        },
        state=AssetState.PENDING.value,
        state_message="New asset created",
    )

    asset = asset_repository.create_asset(asset_data, setup_user.id)

    assert asset.name == asset_data.name
    assert asset.filename == asset_data.filename
    assert asset.mime_type == asset_data.mime_type
    assert asset.size == asset_data.size
    assert asset.user_id == setup_user.id
    assert asset.labels["type"] == "contract"
    assert asset.labels["status"] == "draft"
    assert asset.state == AssetState.PENDING.value
    assert asset.state_message == "New asset created"


def test_get_asset(asset_repository, test_asset):
    """Test retrieving an asset by ID."""
    retrieved_asset = asset_repository.get_asset(test_asset.id)

    assert retrieved_asset is not None
    assert retrieved_asset.id == test_asset.id
    assert retrieved_asset.name == test_asset.name
    assert retrieved_asset.state == test_asset.state
    assert retrieved_asset.state_message == test_asset.state_message


def test_get_user_assets(
    asset_repository,
    test_user,
    test_asset,
):
    """Test retrieving all assets for a user."""
    assets = asset_repository.get_user_assets(test_user.id)

    assert len(assets) == 1
    assert assets[0].user_id == test_user.id
    assert assets[0].name == test_asset.name


def test_update_asset(asset_repository, test_asset):
    """Test updating an asset."""
    update_data = AssetUpdate(
        name="Updated Asset",
        labels={
            "type": "contract",
            "status": "signed",
        },
        state=AssetState.FAILED.value,
        state_message="Asset update failed",
    )

    updated_asset = asset_repository.update_asset(test_asset.id, update_data)

    assert updated_asset.name == "Updated Asset"
    assert len(updated_asset.labels) == 2
    assert updated_asset.labels["status"] == "signed"
    assert updated_asset.state == AssetState.FAILED.value
    assert updated_asset.state_message == "Asset update failed"


def test_delete_asset(asset_repository, test_asset):
    """Test deleting an asset."""
    result = asset_repository.delete_asset(test_asset.id)

    assert result is True
    assert asset_repository.get_asset(test_asset.id) is None


def test_search_assets(
    asset_repository,
    test_user,
    setup_user,
    test_asset,
):
    """Test searching assets with the unified search functionality."""
    # Test search by user_id only
    query = AssetSearchQuery(user_id=test_user.id)
    results = asset_repository.search(query)
    assert len(results) == 1  # All three test assets belong to setup_user
    assert results[0].user_id == test_user.id

    # Test search by labels only
    query = AssetSearchQuery(labels={"category": "test"})
    results = asset_repository.search(query)
    assert len(results) == 1  # One asset is a contract
    assert results[0].labels["category"] == "test"

    # Test search by state only
    query = AssetSearchQuery(state=AssetState.PENDING.value)
    results = asset_repository.search(query)
    assert len(results) == 1
    assert results[0].state == AssetState.PENDING.value

    # Test search by user_id and labels
    query = AssetSearchQuery(user_id=test_user.id, labels={"category": "test"})
    results = asset_repository.search(query)
    assert len(results) == 1
    assert results[0].user_id == test_user.id
    assert results[0].labels["category"] == "test"

    # Test search by user_id, labels, and state
    query = AssetSearchQuery(
        user_id=test_user.id,
        labels={"category": "test"},
        state=AssetState.PENDING.value,
    )
    results = asset_repository.search(query)
    assert len(results) == 1
    assert results[0].user_id == test_user.id
    assert results[0].labels["category"] == "test"
    assert results[0].state == AssetState.PENDING.value

    # Test pagination
    query = AssetSearchQuery(user_id=test_user.id, limit=2)
    results = asset_repository.search(query)
    assert len(results) == 1

    # Test search with no filters (should return all assets)
    query = AssetSearchQuery()
    results = asset_repository.search(query)
    assert len(results) == 1  # All three test assets
