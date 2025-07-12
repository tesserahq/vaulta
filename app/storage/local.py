import shutil
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException
from app.config import get_settings
from app.utils.token_utils import generate_token, verify_token

from .base import StorageBackend

# Constants
PRIVATE_FILES_SALT = "private-files"


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(
        self,
        storage_dir: str = "storage",
        public_url_prefix: str = "/files",
        master_secret_key: Optional[str] = None,
        expires_in: int = 3600,
    ):
        self.storage_dir = Path(storage_dir)
        self.private_dir = self.storage_dir / "private"
        self.public_url_prefix = public_url_prefix
        self.master_secret_key = master_secret_key or get_settings().master_secret_key

        # Create storage directories if they don't exist
        self.private_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, asset_id: str, file: UploadFile) -> str:
        """Save a file to the local filesystem."""
        target_dir = self.private_dir
        file_path = target_dir / str(asset_id)  # Convert UUID to string

        # Ensure the file doesn't already exist
        if file_path.exists():
            raise HTTPException(status_code=400, detail="File already exists")

        # Save the file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return asset_id

    async def get_url(self, asset_id: str) -> str:
        """Get a URL for accessing the file."""
        # For private files, generate a signed URL
        token = generate_token(
            str(asset_id), self.master_secret_key, salt="", expires_in=3600
        )
        return f"/download/{token}"

    async def delete(self, filename: str) -> bool:
        """Delete a file from storage."""
        file_path = self.private_dir / filename
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def verify_token(self, token: str, max_age: int = 3600) -> str:
        """
        Verify a signed token and return the file ID.

        Args:
            token: The signed token to verify
            max_age: Maximum age of the token in seconds

        Returns:
            str: The file ID if the token is valid

        Raises:
            HTTPException: If the token is invalid or expired
        """
        return verify_token(token, self.master_secret_key, salt="", max_age=max_age)
