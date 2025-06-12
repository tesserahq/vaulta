import os
import shutil
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException
from itsdangerous import URLSafeTimedSerializer
from app.config import get_settings

from .base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""
    
    def __init__(
        self,
        storage_dir: str = "storage",
        public_url_prefix: str = "/files",
        secret_key: Optional[str] = None,
    ):
        self.storage_dir = Path(storage_dir)
        self.public_dir = self.storage_dir / "public"
        self.private_dir = self.storage_dir / "private"
        self.public_url_prefix = public_url_prefix
        self.secret_key = secret_key or get_settings().secret_key
        
        # Create storage directories if they don't exist
        self.public_dir.mkdir(parents=True, exist_ok=True)
        self.private_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize serializer for signed URLs
        self.serializer = URLSafeTimedSerializer(self.secret_key)
    
    async def save(self, filename: str, file: UploadFile, is_public: bool = False) -> str:
        """Save a file to the local filesystem."""
        target_dir = self.public_dir if is_public else self.private_dir
        file_path = target_dir / filename
        
        # Ensure the file doesn't already exist
        if file_path.exists():
            raise HTTPException(status_code=400, detail="File already exists")
        
        # Save the file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return filename
    
    async def get_url(self, filename: str, is_public: bool = False, expires_in: int = 3600) -> str:
        """Get a URL for accessing the file."""
        if is_public:
            return f"{self.public_url_prefix}/{filename}"
        
        # For private files, generate a signed URL
        token = self.serializer.dumps(filename, salt="private-files")
        return f"/download/{token}"
    
    async def delete(self, filename: str) -> bool:
        """Delete a file from storage."""
        # Try both public and private directories
        for directory in [self.public_dir, self.private_dir]:
            file_path = directory / filename
            if file_path.exists():
                file_path.unlink()
                return True
        return False
    
    def verify_token(self, token: str, max_age: int = 3600) -> str:
        """Verify a signed token and return the filename."""
        try:
            return self.serializer.loads(token, salt="private-files", max_age=max_age)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid or expired token") 