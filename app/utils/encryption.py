"""Encryption utilities for sensitive data."""

import json
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
from app.config import get_settings


def get_encryption_key() -> bytes:
    """
    Get or derive the encryption key from settings.

    Uses MASTER_SECRET_KEY from settings if available, otherwise
    derives a key from a default value (for development only).

    Returns:
        bytes: Encryption key suitable for Fernet
    """
    settings = get_settings()

    if settings.master_secret_key:
        # Use PBKDF2 to derive a 32-byte key from the master secret
        # This ensures compatibility with Fernet which requires a URL-safe base64-encoded 32-byte key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"vaulta_encryption_salt",  # Fixed salt for consistency
            iterations=100000,
            backend=default_backend(),
        )
        key = kdf.derive(settings.master_secret_key.encode())
        return base64.urlsafe_b64encode(key)
    else:
        # Development fallback - should not be used in production
        # In production, MASTER_SECRET_KEY must be set
        raise ValueError(
            "MASTER_SECRET_KEY must be set in environment variables for encryption"
        )


def encrypt_data(data: Dict[str, Any]) -> Optional[str]:
    """
    Encrypt a dictionary of data.

    Args:
        data: Dictionary to encrypt

    Returns:
        str: Base64-encoded encrypted string, or None if data is None/empty
    """
    if not data:
        return None

    key = get_encryption_key()
    fernet = Fernet(key)

    # Serialize to JSON string, then encrypt
    json_str = json.dumps(data)
    encrypted_bytes = fernet.encrypt(json_str.encode())

    # Return as base64 string for storage in database
    return encrypted_bytes.decode("utf-8")


def decrypt_data(encrypted_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Decrypt a base64-encoded encrypted string back to a dictionary.

    Args:
        encrypted_str: Base64-encoded encrypted string from database

    Returns:
        Dict[str, Any]: Decrypted dictionary, or None if encrypted_str is None/empty
    """
    if not encrypted_str:
        return None

    try:
        key = get_encryption_key()
        fernet = Fernet(key)

        # Decrypt the bytes
        decrypted_bytes = fernet.decrypt(encrypted_str.encode("utf-8"))

        # Deserialize from JSON
        return json.loads(decrypted_bytes.decode("utf-8"))
    except Exception as e:
        # If decryption fails, raise an error
        raise ValueError(f"Failed to decrypt data: {str(e)}")
