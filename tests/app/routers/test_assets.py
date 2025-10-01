import pytest
from uuid import uuid4
from unittest.mock import patch, AsyncMock, Mock
import httpx


class TestAssetsRouter:
    def test_get_asset_success(self, client, setup_asset):
        """Test retrieving an asset by UUID successfully."""
        asset_id = setup_asset.id

        response = client.get(f"/assets/{asset_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(asset_id)
        assert data["name"] == setup_asset.name
        assert data["filename"] == setup_asset.filename
        assert data["mime_type"] == setup_asset.mime_type
        assert data["size"] == setup_asset.size
        assert data["labels"] == setup_asset.labels
        assert data["state"] == setup_asset.state
        assert data["state_message"] == setup_asset.state_message

    def test_get_asset_not_found(self, client):
        """Test retrieving a non-existent asset returns 404."""
        non_existent_id = uuid4()

        response = client.get(f"/assets/{non_existent_id}")
        assert response.status_code == 404
        assert "Asset not found" in response.json()["detail"]

    def test_get_asset_invalid_uuid(self, client):
        """Test retrieving an asset with invalid UUID format returns 422."""
        response = client.get("/assets/invalid-uuid")
        assert response.status_code == 422
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

    @patch("httpx.AsyncClient.get")
    def test_create_asset_from_url_success(self, mock_get, client):
        """Test downloading an asset from URL successfully."""
        # Mock the HTTP response
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock(return_value=None)
        mock_response.content = b"fake file content"
        mock_response.headers = {
            "content-type": "image/png",
            "content-disposition": 'attachment; filename="test.png"',
        }
        mock_get.return_value = mock_response

        request_data = {
            "url": "https://www.hello.com/some-file.png",
            "name": "My Downloaded File",
            "labels": {"source": "external", "category": "image"},
        }

        response = client.post("/assets/from-url", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert "asset_id" in data
        assert "url" in data
        assert "serve_url" in data
        assert data["name"] == "My Downloaded File"
        assert data["filename"] == "test.png"
        assert data["mime_type"] == "image/png"
        assert data["labels"]["source"] == "external"
        assert data["labels"]["category"] == "image"

    @patch("httpx.AsyncClient.get")
    def test_create_asset_from_url_invalid_url(self, mock_get, client):
        """Test downloading an asset with invalid URL."""
        request_data = {"url": "invalid-url", "name": "Test File"}

        response = client.post("/assets/from-url", json=request_data)
        assert response.status_code == 400
        assert "Invalid URL format" in response.json()["detail"]

    @patch("httpx.AsyncClient.get")
    def test_create_asset_from_url_http_error(self, mock_get, client):
        """Test downloading an asset when HTTP request fails."""
        # Mock HTTP error
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "404 Not Found",
                request=AsyncMock(),
                response=AsyncMock(status_code=404),
            )
        )
        mock_get.return_value = mock_response

        request_data = {
            "url": "https://www.hello.com/nonexistent-file.png",
            "name": "Test File",
        }

        response = client.post("/assets/from-url", json=request_data)
        assert response.status_code == 400
        assert "Failed to download file from URL: HTTP 404" in response.json()["detail"]

    @patch("httpx.AsyncClient.get")
    def test_create_asset_from_url_network_error(self, mock_get, client):
        """Test downloading an asset when network request fails."""
        # Mock network error
        mock_get.side_effect = httpx.RequestError("Connection failed")

        request_data = {
            "url": "https://www.hello.com/some-file.png",
            "name": "Test File",
        }

        response = client.post("/assets/from-url", json=request_data)
        assert response.status_code == 400
        assert (
            "Failed to download file from URL: Connection failed"
            in response.json()["detail"]
        )

    @patch("httpx.AsyncClient.get")
    def test_create_asset_from_url_minimal_request(self, mock_get, client):
        """Test downloading an asset with minimal request (only URL)."""
        # Mock the HTTP response
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock(return_value=None)
        mock_response.content = b"fake file content"
        mock_response.headers = {"content-type": "application/pdf"}
        mock_get.return_value = mock_response

        request_data = {"url": "https://www.hello.com/document.pdf"}

        response = client.post("/assets/from-url", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert "asset_id" in data
        assert data["filename"] == "document.pdf"  # Extracted from URL
        assert data["mime_type"] == "application/pdf"
