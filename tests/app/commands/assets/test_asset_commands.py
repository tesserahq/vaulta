from unittest.mock import Mock
from uuid import uuid4

from app.commands.assets.create_asset_command import CreateAssetCommand
from app.commands.assets.delete_asset_command import DeleteAssetCommand
from app.commands.assets.update_asset_command import UpdateAssetCommand
from app.constants.asset import AssetState
from app.schemas.asset import AssetCreate, AssetUpdate


class TestCreateAssetCommand:
    def test_create_does_not_touch_cache(self, db, setup_user):
        cache = Mock()
        command = CreateAssetCommand(db, cache=cache)

        asset = command.execute(
            AssetCreate(
                name="Avatar",
                filename="avatar.png",
                mime_type="image/png",
                size=10,
                state=AssetState.PENDING.value,
            ),
            setup_user.id,
        )

        assert asset.id is not None
        cache.invalidate.assert_not_called()


class TestUpdateAssetCommand:
    def test_update_invalidates_cache_for_that_asset(self, db, setup_asset):
        cache = Mock()
        command = UpdateAssetCommand(db, cache=cache)

        updated = command.execute(setup_asset.id, AssetUpdate(name="Renamed"))

        assert updated.name == "Renamed"
        cache.invalidate.assert_called_once_with(setup_asset.id)

    def test_update_of_missing_asset_does_not_invalidate_cache(self, db):
        cache = Mock()
        command = UpdateAssetCommand(db, cache=cache)

        updated = command.execute(uuid4(), AssetUpdate(name="Renamed"))

        assert updated is None
        cache.invalidate.assert_not_called()


class TestDeleteAssetCommand:
    def test_delete_invalidates_cache_for_that_asset(self, db, setup_asset):
        cache = Mock()
        command = DeleteAssetCommand(db, cache=cache)

        deleted = command.execute(setup_asset.id)

        assert deleted is True
        cache.invalidate.assert_called_once_with(setup_asset.id)

    def test_delete_of_missing_asset_does_not_invalidate_cache(self, db):
        cache = Mock()
        command = DeleteAssetCommand(db, cache=cache)

        deleted = command.execute(uuid4())

        assert deleted is False
        cache.invalidate.assert_not_called()
