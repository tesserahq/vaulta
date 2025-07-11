import pytest
from app.models.asset import Asset

from app.constants.asset import AssetState


@pytest.fixture(scope="function")
def test_asset(db, test_user):
    """Create a test asset for use in tests."""
    asset_data = {
        "name": "Test File",
        "filename": "test_asset.pdf",
        "mime_type": "application/pdf",
        "size": 1024,  # 1KB
        "user_id": test_user.id,
        "labels": {"category": "test", "type": "pdf"},
        "state": AssetState.PENDING.value,
        "state_message": "Asset processed successfully",
    }

    asset = Asset(**asset_data)
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return asset


@pytest.fixture(scope="function")
def setup_asset(db, setup_user):
    """Create a test asset for use in tests."""
    asset_data = {
        "name": "Setup File",
        "filename": "setup_asset.pdf",
        "mime_type": "application/pdf",
        "size": 2048,  # 2KB
        "user_id": setup_user.id,
        "labels": {"category": "setup", "type": "pdf"},
        "state": AssetState.PENDING.value,
        "state_message": "File processed successfully",
    }

    asset = Asset(**asset_data)
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return asset


@pytest.fixture(scope="function")
def setup_another_asset(db, setup_another_user):
    """Create another test file for use in tests."""
    asset_data = {
        "name": "Another File",
        "filename": "another_document.pdf",
        "mime_type": "application/pdf",
        "size": 3072,  # 3KB
        "user_id": setup_another_user.id,
        "labels": {"category": "another", "type": "pdf"},
        "state": AssetState.PENDING.value,
        "state_message": "File processed successfully",
    }

    asset = Asset(**asset_data)
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return asset
