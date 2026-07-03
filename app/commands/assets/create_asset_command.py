import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.cache.asset_cache import AssetCache
from app.cache.factory import AssetCacheFactory
from app.models.asset import Asset
from app.repositories.asset_repository import AssetRepository
from app.schemas.asset import AssetCreate


class CreateAssetCommand:
    def __init__(self, db: Session, cache: Optional[AssetCache] = None):
        self.db = db
        self.asset_repository = AssetRepository(db)
        self.cache = cache or AssetCacheFactory.get_cache()
        self.logger = logging.getLogger(__name__)

    def execute(self, data: AssetCreate, user_id: UUID) -> Asset:
        try:
            return self.asset_repository.create_asset(data, user_id)
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create asset: {str(e)}")
