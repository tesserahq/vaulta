import shutil
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException
from itsdangerous.url_safe import URLSafeTimedSerializer
from app.config import get_settings

from .base import StorageBackend

# Constants
PRIVATE_FILES_SALT = "private-files"


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(
        self,
        storage_dir: str = "storage",
        public_url_prefix: str = "/files",
        secret_key: Optional[str] = None,
        expires_in: int = 3600,
    ):
        self.storage_dir = Path(storage_dir)
        self.private_dir = self.storage_dir / "private"
        self.public_url_prefix = public_url_prefix
        self.secret_key = secret_key or get_settings().secret_key

        # Create storage directories if they don't exist
        self.private_dir.mkdir(parents=True, exist_ok=True)

        # Initialize serializer for signed URLs
        self.serializer = URLSafeTimedSerializer(self.secret_key)

    async def save(self, document_id: str, file: UploadFile) -> str:
        """Save a file to the local filesystem."""
        target_dir = self.private_dir
        file_path = target_dir / str(document_id)  # Convert UUID to string

        # Ensure the file doesn't already exist
        if file_path.exists():
            raise HTTPException(status_code=400, detail="File already exists")

        # Save the file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return document_id

    async def get_url(self, document_id: str) -> str:
        """Get a URL for accessing the file."""
        # For private files, generate a signed URL
        token = self.serializer.dumps(str(document_id))
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
        Verify a signed token and return the document ID.

        Args:
            token: The signed token to verify
            max_age: Maximum age of the token in seconds

        Returns:
            str: The document ID if the token is valid

        Raises:
            HTTPException: If the token is invalid or expired
        """
        try:
            return self.serializer.loads(token, max_age=max_age)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid or expired token: {str(e)}"
            )
