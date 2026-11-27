"""Tests for the asset processing task, called with the test db fixture the way
looply's task tests are: no broker or worker needed."""

from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.constants.asset import AssetState
from app.repositories.asset_repository import AssetRepository
from app.services.processors.base import AssetProcessor, ProcessorContext
from app.tasks.process_asset import _process_asset, process_asset_task


class FakeProcessor(AssetProcessor):
    def __init__(self, result: dict[str, Any]):
        self.result = result
        self.calls: list[tuple] = []

    def process(self, file_bytes, content_type, asset_url, ctx):
        self.calls.append((file_bytes, content_type, asset_url, ctx))
        return self.result


@pytest.fixture
def storage():
    backend = Mock()
    backend.read.return_value = b"%PDF-1.4 bytes"
    backend.get_url.return_value = "https://storage.example.com/asset"
    return backend


@pytest.fixture
def processing_asset(db, setup_asset):
    setup_asset.state = AssetState.PROCESSING.value
    db.commit()
    return setup_asset


@pytest.fixture
def ctx(setup_user):
    return ProcessorContext(user_id=setup_user.id, project_id="project-1")


def _run(
    db,
    storage,
    asset_id,
    ctx,
    processors,
    extract_data=True,
    summarize=True,
    provider=None,
    provider_params=None,
):
    with patch(
        "app.tasks.process_asset.build_processors", return_value=processors
    ) as build:
        _process_asset(
            db,
            storage,
            asset_id,
            extract_data,
            summarize,
            None,
            ctx,
            provider,
            provider_params,
        )
    return build


def test_success_saves_results_and_completes(db, storage, processing_asset, ctx):
    extractor = FakeProcessor({"extracted_data": {"name": "Harry"}})
    summarizer = FakeProcessor({"summary": {"text": "A will."}})

    build = _run(db, storage, processing_asset.id, ctx, [extractor, summarizer])

    build.assert_called_once_with(None, True, True, provider=None, provider_params=None)
    storage.read.assert_called_once_with(str(processing_asset.id))
    assert extractor.calls == [
        (
            b"%PDF-1.4 bytes",
            "application/pdf",
            "https://storage.example.com/asset",
            ctx,
        )
    ]
    asset = AssetRepository(db).get_asset(processing_asset.id)
    assert asset.state == AssetState.COMPLETED.value
    assert asset.extracted_data == {"name": "Harry"}
    assert asset.summary == {"text": "A will."}


def test_upload_override_reaches_build_processors(db, storage, processing_asset, ctx):
    extractor = FakeProcessor({"extracted_data": {"schema_version": "will.v1"}})

    build = _run(
        db,
        storage,
        processing_asset.id,
        ctx,
        [extractor],
        summarize=False,
        provider="modela",
        provider_params={"model": "will-scan"},
    )

    build.assert_called_once_with(
        None,
        True,
        False,
        provider="modela",
        provider_params={"model": "will-scan"},
    )


def test_empty_result_marks_processing_failed_and_keeps_the_rest(
    db, storage, processing_asset, ctx
):
    extractor = FakeProcessor({})  # processors swallow errors and return nothing
    summarizer = FakeProcessor({"summary": {"text": "A will."}})

    _run(db, storage, processing_asset.id, ctx, [extractor, summarizer])

    asset = AssetRepository(db).get_asset(processing_asset.id)
    assert asset.state == AssetState.PROCESSING_FAILED.value
    assert "data extraction" in asset.state_message
    assert asset.summary == {"text": "A will."}


def test_asset_not_processing_is_skipped(db, storage, setup_asset, ctx):
    setup_asset.state = AssetState.COMPLETED.value
    db.commit()
    extractor = FakeProcessor({"extracted_data": {"x": 1}})

    _run(db, storage, setup_asset.id, ctx, [extractor])

    assert extractor.calls == []
    storage.read.assert_not_called()


def test_deleted_asset_is_skipped(db, storage, ctx):
    extractor = FakeProcessor({"extracted_data": {"x": 1}})

    _run(db, storage, uuid4(), ctx, [extractor])

    assert extractor.calls == []


def test_missing_config_raises(db, storage, processing_asset, ctx):
    with pytest.raises(ValueError, match="no longer exists"):
        _process_asset(db, storage, processing_asset.id, True, False, uuid4(), ctx)


def test_task_records_processing_failed_when_processing_raises(
    db, processing_asset, setup_user
):
    @contextmanager
    def test_session_scope():
        yield db

    with (
        patch("app.tasks.process_asset.session_scope", test_session_scope),
        patch("app.tasks.process_asset.StorageFactory.get_backend") as get_backend,
    ):
        get_backend.return_value.read.side_effect = OSError("bucket gone")
        with patch(
            "app.tasks.process_asset.build_processors",
            return_value=[FakeProcessor({})],
        ):
            with pytest.raises(OSError):
                process_asset_task(
                    str(processing_asset.id),
                    True,
                    False,
                    None,
                    str(setup_user.id),
                    "project-1",
                )

    asset = AssetRepository(db).get_asset(processing_asset.id)
    assert asset.state == AssetState.PROCESSING_FAILED.value
    assert asset.state_message == (
        "Processing failed: internal error during processing"
    )
    assert "bucket gone" not in asset.state_message
