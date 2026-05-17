from unittest.mock import MagicMock, patch

import pytest

from app.storage.s3 import S3StorageBackend


@pytest.fixture
def s3_backend():
    with patch("app.storage.s3.boto3") as mock_boto3:
        mock_boto3.client.return_value = MagicMock()
        yield S3StorageBackend(
            bucket_name="test-bucket",
            region_name="us-east-1",
            aws_access_key_id="fake-key",
            aws_secret_access_key="fake-secret",
        )


class TestS3StorageBackend:
    def test_instantiates_successfully(self, s3_backend):
        assert s3_backend.bucket_name == "test-bucket"

    @pytest.mark.asyncio
    async def test_save_calls_upload_fileobj(self, s3_backend):
        from io import BytesIO
        from unittest.mock import AsyncMock

        from fastapi import UploadFile

        file = UploadFile(filename="test.pdf", file=BytesIO(b"content"))
        result = await s3_backend.save("asset-123", file)
        assert result == "asset-123"
        s3_backend.s3.upload_fileobj.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_url_presigned_for_private(self, s3_backend):
        s3_backend.s3.generate_presigned_url.return_value = "https://presigned-url"
        url = await s3_backend.get_url("asset-123")
        assert url == "https://presigned-url"
        s3_backend.s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "asset-123"},
            ExpiresIn=3600,
        )

    @pytest.mark.asyncio
    async def test_get_url_direct_for_public(self, s3_backend):
        url = await s3_backend.get_url("asset-123", is_public=True)
        assert url == "https://test-bucket.s3.amazonaws.com/asset-123"

    @pytest.mark.asyncio
    async def test_delete_returns_true_on_success(self, s3_backend):
        result = await s3_backend.delete("asset-123")
        assert result is True
        s3_backend.s3.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="asset-123"
        )
