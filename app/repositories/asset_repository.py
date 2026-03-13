from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetUpdate, AssetSearchQuery


class AssetRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_asset(self, asset_id: UUID) -> Optional[Asset]:
        """Get an asset by its ID."""
        return self.db.query(Asset).filter(Asset.id == asset_id).first()

    def get_user_assets(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Asset]:
        """Get all assets for a specific user."""
        query = AssetSearchQuery(user_id=user_id, skip=skip, limit=limit)
        return self.search(query)

    def create_asset(self, asset: AssetCreate, user_id: UUID) -> Asset:
        """Create a new asset."""
        db_asset = Asset(**asset.model_dump(), user_id=user_id)
        self.db.add(db_asset)
        self.db.commit()
        self.db.refresh(db_asset)
        return db_asset

    def update_asset(self, asset_id: UUID, asset: AssetUpdate) -> Optional[Asset]:
        """Update an existing asset."""
        db_asset = self.db.query(Asset).filter(Asset.id == asset_id).first()
        if db_asset:
            update_data = asset.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_asset, key, value)
            self.db.commit()
            self.db.refresh(db_asset)
        return db_asset

    def delete_asset(self, asset_id: UUID) -> bool:
        """Delete an asset."""
        db_asset = self.db.query(Asset).filter(Asset.id == asset_id).first()
        if db_asset:
            self.db.delete(db_asset)
            self.db.commit()
            return True
        return False

    def search(self, query: AssetSearchQuery) -> List[Asset]:
        """
        Search assets by user_id, labels, and/or state.

        Args:
            query: AssetSearchQuery object containing search parameters
                - user_id: Optional UUID to filter by asset owner
                - labels: Optional dictionary of labels to match
                - state: Optional state to filter by
                - skip: Number of records to skip (for pagination)
                - limit: Maximum number of records to return

        Returns:
            List[Asset]: List of assets matching the search criteria
        """
        db_query = self.db.query(Asset)

        # Apply user_id filter if provided
        if query.user_id:
            db_query = db_query.filter(Asset.user_id == query.user_id)

        # Apply labels filter if provided
        if query.labels:
            db_query = db_query.filter(Asset.labels.op("@>")(query.labels))

        # Apply state filter if provided
        if query.state:
            db_query = db_query.filter(Asset.state == query.state)

        return db_query.offset(query.skip).limit(query.limit).all()
