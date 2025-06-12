from typing import Optional
from .base import StorageBackend
from .local import LocalStorageBackend
from .s3 import S3StorageBackend
from app.config import get_settings


class StorageFactory:
    """Factory for creating storage backends."""
    
    _instance: Optional[StorageBackend] = None
    
    @classmethod
    def get_backend(cls) -> StorageBackend:
        """
        Get or create a storage backend instance.
        
        Returns:
            StorageBackend: The configured storage backend instance
        """
        if cls._instance is None:
            cls._instance = cls._create_backend()
        return cls._instance
    
    @classmethod
    def _create_backend(cls) -> StorageBackend:
        """
        Create a new storage backend instance based on configuration.
        
        Returns:
            StorageBackend: A new storage backend instance
        """
        settings = get_settings()
        if settings.storage_backend == "s3":
            return S3StorageBackend(
                bucket_name=settings.s3_bucket_name,
                region_name=settings.s3_region_name,
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
        else:
            return LocalStorageBackend(
                storage_dir=settings.local_storage_dir,
                public_url_prefix=settings.public_url_prefix,
            )
    
    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance. Useful for testing."""
        cls._instance = None 