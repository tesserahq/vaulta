import pytest
from uuid import uuid4


class TestAssetsRouter:
    def test_delete_asset_success(self, client, setup_asset):
        """Test deleting an asset successfully."""
        asset_id = setup_asset.id

        response = client.delete(f"/assets/{asset_id}")
        assert response.status_code == 200

        data = response.json()
        assert "message" in data
        assert data["message"] == "Asset deleted successfully"
        assert "details" in data
        assert data["details"]["asset_id"] == str(asset_id)

    def test_delete_asset_not_found(self, client):
        """Test deleting a non-existent asset."""
        non_existent_id = uuid4()

        response = client.delete(f"/assets/{non_existent_id}")
        assert response.status_code == 404
        assert "Asset not found" in response.json()["detail"]

    def test_delete_asset_not_authorized(self, client, setup_another_asset):
        """Test deleting an asset owned by another user."""
        asset_id = setup_another_asset.id

        response = client.delete(f"/assets/{asset_id}")
        assert response.status_code == 403
        assert "Not authorized to delete this asset" in response.json()["detail"]

    def test_delete_asset_invalid_uuid(self, client):
        """Test deleting an asset with invalid UUID format."""
        response = client.delete("/assets/invalid-uuid")
        assert response.status_code == 422  # Validation error for invalid UUID
