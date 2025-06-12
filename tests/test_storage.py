import pytest
from fastapi import UploadFile
from pathlib import Path
import os
from app.storage.local import LocalStorageBackend
from app.storage.s3 import S3StorageBackend
from app.storage.factory import StorageFactory
from app.config import get_settings


@pytest.fixture
def local_storage():
    """Create a local storage backend for testing."""
    storage_dir = "test_storage"
    storage = LocalStorageBackend(storage_dir=storage_dir, secret_key=get_settings().secret_key)
    yield storage
    # Cleanup after tests
    if os.path.exists(storage_dir):
        for root, dirs, files in os.walk(storage_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(storage_dir)


@pytest.mark.asyncio
async def test_local_storage_public_file(local_storage):
    """Test saving and retrieving a public file."""
    # Create a test file
    content = b"test content"
    file = UploadFile(
        filename="test.txt",
        file=type("obj", (object,), {"read": lambda: content})()
    )
    
    # Save the file
    filename = await local_storage.save("test.txt", file, is_public=True)
    assert filename == "test.txt"
    
    # Get the URL
    url = await local_storage.get_url(filename, is_public=True)
    assert url == "/files/test.txt"
    
    # Verify file exists
    assert (local_storage.public_dir / filename).exists()


@pytest.mark.asyncio
async def test_local_storage_private_file(local_storage):
    """Test saving and retrieving a private file."""
    # Create a test file
    content = b"private content"
    file = UploadFile(
        filename="private.txt",
        file=type("obj", (object,), {"read": lambda: content})()
    )
    
    # Save the file
    filename = await local_storage.save("private.txt", file, is_public=False)
    assert filename == "private.txt"
    
    # Get the URL
    url = await local_storage.get_url(filename, is_public=False)
    assert url.startswith("/download/")
    
    # Extract token from URL
    token = url.split("/")[-1]
    
    # Verify token
    verified_filename = local_storage.verify_token(token)
    assert verified_filename == filename
    
    # Verify file exists
    assert (local_storage.private_dir / filename).exists()


@pytest.mark.asyncio
async def test_local_storage_delete(local_storage):
    """Test deleting a file."""
    # Create and save a test file
    content = b"test content"
    file = UploadFile(
        filename="test.txt",
        file=type("obj", (object,), {"read": lambda: content})()
    )
    filename = await local_storage.save("test.txt", file)
    
    # Delete the file
    success = await local_storage.delete(filename)
    assert success is True
    
    # Verify file is gone
    assert not (local_storage.private_dir / filename).exists()


def test_storage_factory_singleton():
    """Test that the storage factory returns the same instance."""
    # Get two instances
    instance1 = StorageFactory.get_backend()
    instance2 = StorageFactory.get_backend()
    
    # They should be the same instance
    assert instance1 is instance2


def test_storage_factory_reset():
    """Test that the storage factory can be reset."""
    # Get initial instance
    instance1 = StorageFactory.get_backend()
    
    # Reset the factory
    StorageFactory.reset()
    
    # Get new instance
    instance2 = StorageFactory.get_backend()
    
    # They should be different instances
    assert instance1 is not instance2 