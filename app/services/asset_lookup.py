from typing import Optional
from uuid import UUID

from app.cache.asset_cache import AssetCache, AssetServeMetadata
from app.repositories.asset_repository import AssetRepository


def get_asset_for_serving(
    asset_id: UUID, repository: AssetRepository, cache: AssetCache
) -> Optional[AssetServeMetadata]:
    """Resolve the metadata needed to serve an asset, preferring the cache.

    Returns None if the asset does not exist (cached negatively either way).
    """
    lookup = cache.read(asset_id)
    if lookup.cached:
        return lookup.metadata

    asset = repository.get_asset(asset_id)
    if asset is None:
        cache.write_not_found(asset_id)
        return None

    metadata = AssetServeMetadata(
        mime_type=str(asset.mime_type), filename=str(asset.filename)
    )
    cache.write_found(asset_id, metadata)
    return metadata
