from typing import Optional

from tessera_sdk.infra.cache import create_cache

from .asset_cache import AssetCache


class AssetCacheFactory:
    """Factory for the singleton AssetCache instance."""

    _instance: Optional[AssetCache] = None

    @classmethod
    def get_cache(cls) -> AssetCache:
        if cls._instance is None:
            cls._instance = AssetCache(create_cache(namespace="assets"))
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance. Useful for testing."""
        cls._instance = None
