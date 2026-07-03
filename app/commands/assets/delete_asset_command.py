import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.cache.asset_cache import AssetCache
from app.cache.factory import AssetCacheFactory
from app.repositories.asset_repository import AssetRepository


class DeleteAssetCommand:
    def __init__(self, db: Session, cache: Optional[AssetCache] = None):
        self.db = db
        self.asset_repository = AssetRepository(db)
        self.cache = cache or AssetCacheFactory.get_cache()
        self.logger = logging.getLogger(__name__)

    def execute(self, asset_id: UUID) -> bool:
        try:
            deleted = self.asset_repository.delete_asset(asset_id)
            if deleted:
                self.cache.invalidate(asset_id)
            return deleted
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to delete asset: {str(e)}")
