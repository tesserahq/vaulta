import pytest
from uuid import uuid4
from unittest.mock import patch, AsyncMock, Mock
import httpx

from app.config import get_settings
from app.repositories.asset_repository import AssetRepository
from app.routers.assets import get_storage_backend
from app.routers.utils.dependencies import get_asset_cache
from app.cache.asset_cache import AssetCache
from app.storage.local import LocalStorageBackend
from app.utils.token_utils import derive_secret, sign_serve_url


class MockStorageBackend:
    """Minimal storage mock for router tests — avoids hitting real S3."""

    async def save(self, asset_id, file, **kwargs):
        return str(asset_id)

    async def get_url(self, asset_id, **kwargs):
        return f"https://mock-storage.example.com/{asset_id}"

    async def delete(self, asset_id, **kwargs):
        return True


@pytest.fixture
def mock_storage_factory():
    backend = MockStorageBackend()
    with patch("app.storage.factory.StorageFactory.get_backend", return_value=backend):
        yield backend


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

    def test_get_asset_cache_hit_skips_repository(self, client, setup_asset):
        """A positive record-cache hit must return the asset without querying the repository."""
        underlying = Mock()
        underlying.read.return_value = {
            "found": True,
            "asset": {
                "id": str(setup_asset.id),
                "user_id": str(setup_asset.user_id),
                "name": setup_asset.name,
                "filename": setup_asset.filename,
                "mime_type": setup_asset.mime_type,
                "size": setup_asset.size,
                "labels": setup_asset.labels,
                "state": setup_asset.state,
                "state_message": setup_asset.state_message,
                "created_at": setup_asset.created_at.isoformat(),
                "updated_at": setup_asset.updated_at.isoformat(),
                "human_readable_size": setup_asset.human_readable_size,
            },
        }
        cache = AssetCache(underlying)

        client.app.dependency_overrides[get_asset_cache] = lambda: cache
        try:
            with patch.object(AssetRepository, "get_asset") as mock_get_asset:
                response = client.get(f"/assets/{setup_asset.id}")

                assert response.status_code == 200
                assert response.json()["id"] == str(setup_asset.id)
                mock_get_asset.assert_not_called()
        finally:
            del client.app.dependency_overrides[get_asset_cache]

    def test_get_asset_cache_miss_populates_record_cache(self, client, setup_asset):
        """A cache miss for an existing asset must populate the record cache."""
        underlying = Mock()
        underlying.read.return_value = None
        cache = AssetCache(underlying)

        client.app.dependency_overrides[get_asset_cache] = lambda: cache
        try:
            response = client.get(f"/assets/{setup_asset.id}")

            assert response.status_code == 200
            underlying.write.assert_called_once()
            key, value = underlying.write.call_args.args
            assert key == f"record:{setup_asset.id}"
            assert value["found"] is True
            assert value["asset"]["id"] == str(setup_asset.id)
            assert underlying.write.call_args.kwargs == {"ttl": 600}
        finally:
            del client.app.dependency_overrides[get_asset_cache]

    def test_get_asset_cache_miss_not_found_populates_negative_entry(self, client):
        """A cache miss for a nonexistent asset must cache the negative result."""
        underlying = Mock()
        underlying.read.return_value = None
        cache = AssetCache(underlying)

        client.app.dependency_overrides[get_asset_cache] = lambda: cache
        try:
            missing_id = uuid4()
            response = client.get(f"/assets/{missing_id}")

            assert response.status_code == 404
            underlying.write.assert_called_once_with(
                f"record:{missing_id}", {"found": False}, ttl=60
            )
        finally:
            del client.app.dependency_overrides[get_asset_cache]

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

    def test_delete_asset_invalidates_cache(self, client, setup_asset):
        """Deleting an asset must invalidate any cached serve-metadata and record entries for it."""
        underlying = Mock()
        underlying.read.return_value = None
        cache = AssetCache(underlying)

        client.app.dependency_overrides[get_asset_cache] = lambda: cache
        try:
            response = client.delete(f"/assets/{setup_asset.id}")

            assert response.status_code == 200
            underlying.delete.assert_any_call(str(setup_asset.id))
            underlying.delete.assert_any_call(f"record:{setup_asset.id}")
        finally:
            del client.app.dependency_overrides[get_asset_cache]

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
    def test_create_asset_from_url_success(
        self, mock_get, client, mock_storage_factory
    ):
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
    def test_create_asset_from_url_minimal_request(
        self, mock_get, client, mock_storage_factory
    ):
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


class TestServeAssetRoute:
    def _sign(self, asset_id, client_id="linden", expires_in=3600):
        master_secret = get_settings().master_secret_key
        derived_secret = derive_secret(client_id, master_secret)
        url = sign_serve_url(asset_id, client_id, expires_in, derived_secret)
        return url.removeprefix("/assets/serve/")

    def test_serve_asset_empty_asset_id_returns_400_not_500(self, client):
        """A validly-signed payload with an empty asset id must not 500."""
        payload = self._sign("")

        response = client.get(f"/assets/serve/{payload}")

        assert response.status_code == 400
        assert "asset id" in response.json()["detail"].lower()

    def test_serve_asset_malformed_asset_id_returns_404_not_500(self, client):
        """A validly-signed payload with a non-UUID asset id must not 500."""
        payload = self._sign("not-a-real-uuid")

        response = client.get(f"/assets/serve/{payload}")

        assert response.status_code == 404
        assert "Asset not found" in response.json()["detail"]

    def test_serve_asset_cache_hit_skips_repository(
        self, client, setup_asset, tmp_path
    ):
        """A positive cache hit must serve the asset without querying the repository."""
        storage = LocalStorageBackend(storage_dir=tmp_path)
        (storage.private_dir / str(setup_asset.id)).write_bytes(b"fake bytes")

        underlying = Mock()
        underlying.read.return_value = {
            "found": True,
            "mime_type": setup_asset.mime_type,
            "filename": setup_asset.filename,
        }
        cache = AssetCache(underlying)

        client.app.dependency_overrides[get_storage_backend] = lambda: storage
        client.app.dependency_overrides[get_asset_cache] = lambda: cache
        try:
            with patch.object(AssetRepository, "get_asset") as mock_get_asset:
                payload = self._sign(str(setup_asset.id))
                response = client.get(f"/assets/serve/{payload}")

                assert response.status_code == 200
                mock_get_asset.assert_not_called()
        finally:
            del client.app.dependency_overrides[get_storage_backend]
            del client.app.dependency_overrides[get_asset_cache]

    def test_serve_asset_cache_miss_populates_positive_cache_entry(
        self, client, setup_asset, tmp_path
    ):
        """A cache miss for an existing asset must query the DB once and populate the cache."""
        storage = LocalStorageBackend(storage_dir=tmp_path)
        (storage.private_dir / str(setup_asset.id)).write_bytes(b"fake bytes")

        underlying = Mock()
        underlying.read.return_value = None
        cache = AssetCache(underlying)

        client.app.dependency_overrides[get_storage_backend] = lambda: storage
        client.app.dependency_overrides[get_asset_cache] = lambda: cache
        try:
            payload = self._sign(str(setup_asset.id))
            response = client.get(f"/assets/serve/{payload}")

            assert response.status_code == 200
            underlying.write.assert_called_once_with(
                str(setup_asset.id),
                {
                    "found": True,
                    "mime_type": setup_asset.mime_type,
                    "filename": setup_asset.filename,
                },
                ttl=600,
            )
        finally:
            del client.app.dependency_overrides[get_storage_backend]
            del client.app.dependency_overrides[get_asset_cache]

    def test_serve_asset_cache_miss_not_found_populates_negative_cache_entry(
        self, client
    ):
        """A cache miss for a nonexistent asset must cache the negative result."""
        underlying = Mock()
        underlying.read.return_value = None
        cache = AssetCache(underlying)

        client.app.dependency_overrides[get_asset_cache] = lambda: cache
        try:
            missing_id = uuid4()
            payload = self._sign(str(missing_id))
            response = client.get(f"/assets/serve/{payload}")

            assert response.status_code == 404
            underlying.write.assert_called_once_with(
                str(missing_id), {"found": False}, ttl=60
            )
        finally:
            del client.app.dependency_overrides[get_asset_cache]
