from abc import ABC, abstractmethod
from fastapi import UploadFile
from typing import Optional


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    async def save(self, filename: str, file: UploadFile, is_public: bool = False) -> str:
        """
        Save a file to storage.
        
        Args:
            filename: The name to save the file as
            file: The file to save
            is_public: Whether the file should be publicly accessible
            
        Returns:
            str: The identifier/key for the saved file
        """
        pass
    
    @abstractmethod
    async def get_url(self, filename: str, is_public: bool = False, expires_in: int = 3600) -> str:
        """
        Get a URL for accessing the file.
        
        Args:
            filename: The identifier/key of the file
            is_public: Whether the file is public
            expires_in: Number of seconds until the URL expires (for private files)
            
        Returns:
            str: The URL to access the file
        """
        pass
    
    @abstractmethod
    async def delete(self, filename: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            filename: The identifier/key of the file to delete
            
        Returns:
            bool: True if deletion was successful
        """
        pass 