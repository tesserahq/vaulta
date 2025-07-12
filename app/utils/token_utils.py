import hashlib
import hmac
from itsdangerous.url_safe import URLSafeTimedSerializer
from fastapi import HTTPException
from typing import Optional
from app.config import get_settings


def generate_token(data: str, secret_key: str, salt: str, expires_in: int) -> str:
    serializer = URLSafeTimedSerializer(secret_key)
    return serializer.dumps(data, salt=salt)


def verify_token(token: str, secret_key: str, salt: str, max_age: int) -> str:
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
    serializer = URLSafeTimedSerializer(secret_key)
    try:
        return serializer.loads(token, salt=salt, max_age=max_age)
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid or expired token")


def derive_secret(client_id: str, master_secret: Optional[str] = None) -> str:
    """
    Derive a service-specific secret from a master secret and client ID.

    Args:
        client_id: The client identifier
        master_secret: The master secret key. If not provided, uses the one from config.

    Returns:
        str: The derived service secret
    """
    if master_secret is None:
        settings = get_settings()
        master_secret = settings.master_secret_key

    return hmac.new(
        master_secret.encode(), client_id.encode(), hashlib.sha256
    ).hexdigest()


def generate_token_with_service(
    data: str,
    client_id: str,
    master_secret: Optional[str] = None,
    salt: str = "",
    expires_in: int = 3600,
) -> str:
    """
    Generate a token with service-specific secret derivation.

    Args:
        data: The data to encode in the token
        client_id: The client identifier
        master_secret: The master secret key. If not provided, uses the one from config.
        salt: The salt for token generation
        expires_in: Token expiration time in seconds

    Returns:
        str: The generated token
    """
    child_secret = derive_secret(client_id, master_secret)
    return generate_token(
        data=f"{client_id}:{data}",
        secret_key=child_secret,
        salt=salt,
        expires_in=expires_in,
    )


def verify_serve_token(
    token: str, master_secret: Optional[str] = None, max_age: int = 31536000
) -> str:
    """
    Verify a signed serve token and return the file ID.

    Args:
        token: The signed serve token to verify
        master_secret: The master secret key. If not provided, uses the one from config.
        max_age: Maximum age of the token in seconds (default: 1 year)

    Returns:
        str: The file ID if the token is valid

    Raises:
        HTTPException: If the token is invalid or expired
    """
    return verify_token_with_service(
        token, master_secret, salt="serve", max_age=max_age
    )


def verify_token_with_service(
    token: str, master_secret: Optional[str] = None, salt: str = "", max_age: int = 3600
) -> str:
    """
    Verify a token with service-specific secret derivation.

    Args:
        token: The token to verify
        master_secret: The master secret key. If not provided, uses the one from config.
        salt: The salt for token verification
        max_age: Maximum age of the token in seconds

    Returns:
        str: The asset ID if the token is valid

    Raises:
        HTTPException: If the token is invalid or expired
    """
    # Decode token just to extract client_id prefix before verifying
    from app.models.client import Client

    for service in Client.all():  # or another way to get known clients
        try:
            child_secret = derive_secret(service.client_id, master_secret)
            raw = verify_token(token, child_secret, salt=salt, max_age=max_age)
            # Ensure the payload has the format 'client_id:asset_id'
            client_id, asset_id = raw.split(":", 1)
            if client_id == service.client_id:
                return asset_id
        except Exception:
            continue
    raise HTTPException(status_code=403, detail="Invalid or expired token")


def generate_serve_token(
    asset_id: str,
    client_id: str,
    master_secret: Optional[str] = None,
    expires_in: int = 31536000,
) -> str:
    """
    Generate a signed token for serving a file publicly.

    Args:
        asset_id: The file ID to generate a token for
        client_id: The service identifier
        master_secret: The master secret key. If not provided, uses the one from config.
        expires_in: Number of seconds until the token expires (default: 1 year)

    Returns:
        str: The signed token for serving the file
    """
    return generate_token_with_service(
        str(asset_id), client_id, master_secret, salt="serve", expires_in=expires_in
    )
