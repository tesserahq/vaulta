from io import BytesIO

from fastapi import UploadFile

from app.storage.local import LocalStorageBackend


def test_read_returns_saved_bytes(tmp_path):
    storage = LocalStorageBackend(storage_dir=tmp_path, master_secret_key="test")
    storage.save("asset-1", UploadFile(filename="a.txt", file=BytesIO(b"hello")))

    assert storage.read("asset-1") == b"hello"
