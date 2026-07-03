from unittest.mock import Mock
from uuid import uuid4

from app.cache.asset_cache import (
    AssetCache,
    AssetServeMetadata,
    POSITIVE_TTL_SECONDS,
    NEGATIVE_TTL_SECONDS,
)


class TestAssetCache:
    def test_read_miss(self):
        underlying = Mock()
        underlying.read.return_value = None
        cache = AssetCache(underlying)
        asset_id = uuid4()

        result = cache.read(asset_id)

        assert result.cached is False
        assert result.metadata is None
        underlying.read.assert_called_once_with(str(asset_id))

    def test_read_positive_hit(self):
        underlying = Mock()
        underlying.read.return_value = {
            "found": True,
            "mime_type": "image/png",
            "filename": "avatar.png",
        }
        cache = AssetCache(underlying)

        result = cache.read(uuid4())

        assert result.cached is True
        assert result.metadata == AssetServeMetadata(
            mime_type="image/png", filename="avatar.png"
        )

    def test_read_negative_hit(self):
        underlying = Mock()
        underlying.read.return_value = {"found": False}
        cache = AssetCache(underlying)

        result = cache.read(uuid4())

        assert result.cached is True
        assert result.metadata is None

    def test_write_found_uses_positive_ttl_and_key(self):
        underlying = Mock()
        cache = AssetCache(underlying)
        asset_id = uuid4()

        cache.write_found(
            asset_id, AssetServeMetadata(mime_type="image/png", filename="a.png")
        )

        underlying.write.assert_called_once_with(
            str(asset_id),
            {"found": True, "mime_type": "image/png", "filename": "a.png"},
            ttl=POSITIVE_TTL_SECONDS,
        )

    def test_write_not_found_uses_negative_ttl_and_key(self):
        underlying = Mock()
        cache = AssetCache(underlying)
        asset_id = uuid4()

        cache.write_not_found(asset_id)

        underlying.write.assert_called_once_with(
            str(asset_id), {"found": False}, ttl=NEGATIVE_TTL_SECONDS
        )

    def test_invalidate_deletes_by_key(self):
        underlying = Mock()
        cache = AssetCache(underlying)
        asset_id = uuid4()

        cache.invalidate(asset_id)

        underlying.delete.assert_called_once_with(str(asset_id))
