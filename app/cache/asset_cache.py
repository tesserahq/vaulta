from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from tessera_sdk.infra.cache import Cache

POSITIVE_TTL_SECONDS = 600  # 10 minutes: backstop behind proactive invalidation
NEGATIVE_TTL_SECONDS = 60  # 1 minute: absorbs retry storms for bad asset ids


@dataclass
class AssetServeMetadata:
    """The subset of an asset's fields needed to serve it via signed URL."""

    mime_type: str
    filename: str


@dataclass
class AssetCacheLookup:
    """Result of a cache read: whether it was cached at all, and if so, what for."""

    cached: bool
    metadata: Optional[AssetServeMetadata] = None
    """Present when cached and the asset was found; None when cached as not-found."""


class AssetCache:
    """Caches asset-serving metadata by asset id, including negative (not-found) results."""

    def __init__(self, cache: Cache):
        self._cache = cache

    def _key(self, asset_id: UUID) -> str:
        return str(asset_id)

    def read(self, asset_id: UUID) -> AssetCacheLookup:
        entry = self._cache.read(self._key(asset_id))
        if entry is None:
            return AssetCacheLookup(cached=False)
        if not entry.get("found"):
            return AssetCacheLookup(cached=True, metadata=None)
        return AssetCacheLookup(
            cached=True,
            metadata=AssetServeMetadata(
                mime_type=entry["mime_type"], filename=entry["filename"]
            ),
        )

    def write_found(self, asset_id: UUID, metadata: AssetServeMetadata) -> None:
        self._cache.write(
            self._key(asset_id),
            {
                "found": True,
                "mime_type": metadata.mime_type,
                "filename": metadata.filename,
            },
            ttl=POSITIVE_TTL_SECONDS,
        )

    def write_not_found(self, asset_id: UUID) -> None:
        self._cache.write(
            self._key(asset_id), {"found": False}, ttl=NEGATIVE_TTL_SECONDS
        )

    def invalidate(self, asset_id: UUID) -> None:
        self._cache.delete(self._key(asset_id))
