from unittest.mock import Mock
from uuid import uuid4

from app.cache.asset_cache import AssetCacheLookup, AssetServeMetadata
from app.repositories.asset_repository import AssetRepository
from app.services.asset_lookup import get_asset_for_serving


class TestGetAssetForServing:
    def test_positive_cache_hit_skips_repository(self, db):
        repository = AssetRepository(db)
        cache = Mock()
        cache.read.return_value = AssetCacheLookup(
            cached=True,
            metadata=AssetServeMetadata(mime_type="image/png", filename="a.png"),
        )

        result = get_asset_for_serving(uuid4(), repository, cache)

        assert result == AssetServeMetadata(mime_type="image/png", filename="a.png")
        cache.write_found.assert_not_called()
        cache.write_not_found.assert_not_called()

    def test_negative_cache_hit_skips_repository(self, db):
        repository = AssetRepository(db)
        cache = Mock()
        cache.read.return_value = AssetCacheLookup(cached=True, metadata=None)

        result = get_asset_for_serving(uuid4(), repository, cache)

        assert result is None
        cache.write_found.assert_not_called()
        cache.write_not_found.assert_not_called()

    def test_cache_miss_found_queries_repository_and_populates_cache(
        self, db, setup_asset
    ):
        repository = AssetRepository(db)
        cache = Mock()
        cache.read.return_value = AssetCacheLookup(cached=False)

        result = get_asset_for_serving(setup_asset.id, repository, cache)

        assert result == AssetServeMetadata(
            mime_type=setup_asset.mime_type, filename=setup_asset.filename
        )
        cache.write_found.assert_called_once_with(setup_asset.id, result)
        cache.write_not_found.assert_not_called()

    def test_cache_miss_not_found_queries_repository_and_caches_negative(self, db):
        repository = AssetRepository(db)
        cache = Mock()
        cache.read.return_value = AssetCacheLookup(cached=False)
        missing_asset_id = uuid4()

        result = get_asset_for_serving(missing_asset_id, repository, cache)

        assert result is None
        cache.write_not_found.assert_called_once_with(missing_asset_id)
        cache.write_found.assert_not_called()
