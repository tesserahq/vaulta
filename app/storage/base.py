from abc import ABC, abstractmethod
from fastapi import UploadFile


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def save(self, document_id: str, file: UploadFile) -> str:
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
    async def get_url(self, document_id: str) -> str:
        """
        Get a URL for accessing the file.

        Args:
            document_id: The identifier/key of the file
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

    @abstractmethod
    def verify_token(self, token: str, max_age: int = 3600) -> str:
        """
        Verify a signed token and return the document ID.

        Args:
            token: The signed token to verify
            max_age: Maximum age of the token in seconds

        Returns:
            str: The document ID if the token is valid

        Raises:
            Exception: If the token is invalid or expired
        """
        pass
