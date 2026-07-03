import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.cache.asset_cache import AssetCache
from app.cache.factory import AssetCacheFactory
from app.models.asset import Asset
from app.repositories.asset_repository import AssetRepository
from app.schemas.asset import AssetUpdate


class UpdateAssetCommand:
    def __init__(self, db: Session, cache: Optional[AssetCache] = None):
        self.db = db
        self.asset_repository = AssetRepository(db)
        self.cache = cache or AssetCacheFactory.get_cache()
        self.logger = logging.getLogger(__name__)

    def execute(self, asset_id: UUID, data: AssetUpdate) -> Optional[Asset]:
        try:
            updated = self.asset_repository.update_asset(asset_id, data)
            if updated is not None:
                self.cache.invalidate(asset_id)
            return updated
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to update asset: {str(e)}")
