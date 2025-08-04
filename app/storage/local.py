import shutil
import os
from pathlib import Path
from typing import Optional, Union
from fastapi import UploadFile, HTTPException
from app.config import get_settings
from app.utils.token_utils import generate_token, verify_token

from .base import StorageBackend

# Constants
PRIVATE_FILES_SALT = "private-files"


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend that supports both relative and absolute paths."""

    def __init__(
        self,
        storage_dir: Union[str, Path] = "storage",
        public_url_prefix: str = "/files",
        master_secret_key: Optional[str] = None,
        expires_in: int = 3600,
    ):
        """
        Initialize the local storage backend.

        Args:
            storage_dir: Storage directory path. Can be:
                - Relative path (e.g., "storage", "files")
                - Absolute path (e.g., "/tmp/myfiles", "/var/storage")
                - Path object
            public_url_prefix: URL prefix for public file access
            master_secret_key: Secret key for signing URLs
            expires_in: Default token expiration time in seconds
        """
        # Convert to Path object and resolve to absolute path
        self.storage_dir = Path(storage_dir).resolve()
        self.private_dir = self.storage_dir / "private"
        self.public_url_prefix = public_url_prefix
        # Get master secret key from parameter or settings, with fallback for development
        self.master_secret_key = (
            master_secret_key or get_settings().master_secret_key or "dev-secret-key"
        )
        self.expires_in = expires_in

        # Validate and create storage directories
        self._ensure_storage_directories()

    def _ensure_storage_directories(self) -> None:
        """Ensure storage directories exist and are writable."""
        try:
            # Create the main storage directory
            self.storage_dir.mkdir(parents=True, exist_ok=True)

            # Create the private directory
            self.private_dir.mkdir(parents=True, exist_ok=True)

            # Test write permissions
            test_file = self.storage_dir / ".test_write"
            test_file.write_text("test")
            test_file.unlink()

        except PermissionError:
            raise HTTPException(
                status_code=500,
                detail=f"Permission denied: Cannot write to storage directory '{self.storage_dir}'",
            )
        except OSError as e:
            raise HTTPException(
                status_code=500, detail=f"Storage directory error: {str(e)}"
            )

    def _validate_file_path(self, file_path: Path) -> None:
        """Validate that the file path is within the storage directory for security."""
        try:
            # Ensure the file path is within the storage directory
            file_path.resolve().relative_to(self.storage_dir.resolve())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid file path: Attempting to access outside storage directory",
            )

    async def save(self, asset_id: str, file: UploadFile) -> str:
        """Save a file to the local filesystem."""
        target_dir = self.private_dir
        file_path = target_dir / str(asset_id)  # Convert UUID to string

        # Validate the file path for security
        self._validate_file_path(file_path)

        # Ensure the file doesn't already exist
        if file_path.exists():
            raise HTTPException(status_code=400, detail="File already exists")

        try:
            # Save the file
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            return asset_id

        except OSError as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to save file: {str(e)}"
            )

    async def get_url(self, asset_id: str) -> str:
        """Get a URL for accessing the file."""
        # For private files, generate a signed URL
        token = generate_token(
            str(asset_id), self.master_secret_key, salt="", expires_in=self.expires_in
        )
        return f"/download/{token}"

    async def delete(self, filename: str) -> bool:
        """Delete a file from storage."""
        file_path = self.private_dir / filename

        # Validate the file path for security
        self._validate_file_path(file_path)

        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except OSError as e:
                raise HTTPException(
                    status_code=500, detail=f"Failed to delete file: {str(e)}"
                )
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

    def get_file_path(self, asset_id: str) -> Path:
        """
        Get the full file path for a given asset ID.

        Args:
            asset_id: The asset ID

        Returns:
            Path: The full file path
        """
        file_path = self.private_dir / str(asset_id)
        self._validate_file_path(file_path)
        return file_path

    @property
    def storage_info(self) -> dict:
        """Get information about the storage configuration."""
        return {
            "storage_dir": str(self.storage_dir),
            "private_dir": str(self.private_dir),
            "storage_dir_absolute": str(self.storage_dir.resolve()),
            "exists": self.storage_dir.exists(),
            "is_writable": os.access(self.storage_dir, os.W_OK),
        }
