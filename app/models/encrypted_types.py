"""SQLAlchemy custom types for encrypted fields."""

from typing import Any, Dict, Optional
from sqlalchemy import TypeDecorator, Text
from app.utils.encryption import encrypt_data, decrypt_data


class EncryptedJSONB(TypeDecorator):
    """
    SQLAlchemy TypeDecorator that encrypts/decrypts JSONB data transparently.

    This type stores encrypted data as TEXT in the database but presents
    it as a dictionary (JSON) to the application layer.

    Usage:
        extracted_data = Column(EncryptedJSONB, default=dict, nullable=True)
    """

    impl = Text
    cache_ok = True

    def process_bind_param(
        self, value: Optional[Dict[str, Any]], dialect
    ) -> Optional[str]:
        """
        Encrypt the value before storing it in the database.

        Args:
            value: Dictionary to encrypt (or None)
            dialect: SQLAlchemy dialect (unused)

        Returns:
            str: Encrypted string to store in database, or None
        """
        if value is None:
            return None

        # Only process dict values
        if not isinstance(value, dict):
            raise TypeError(f"Expected dict, got {type(value).__name__}")

        # Encrypt the data (empty dicts will return None from encrypt_data)
        return encrypt_data(value)

    def process_result_value(
        self, value: Optional[str], dialect
    ) -> Optional[Dict[str, Any]]:
        """
        Decrypt the value when reading from the database.

        Args:
            value: Encrypted string from database (or None)
            dialect: SQLAlchemy dialect (unused)

        Returns:
            Dict[str, Any]: Decrypted dictionary, or empty dict if value was None
        """
        if value is None:
            return {}

        # Decrypt the data
        decrypted = decrypt_data(value)
        return decrypted if decrypted is not None else {}
