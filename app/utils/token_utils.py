import hashlib
import hmac
from itsdangerous.url_safe import URLSafeTimedSerializer
from fastapi import HTTPException


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


def derive_service_secret(client_id: str, master_secret: str) -> str:
    return hmac.new(
        master_secret.encode(), client_id.encode(), hashlib.sha256
    ).hexdigest()


def generate_token_with_service(
    data: str, client_id: str, master_secret: str, salt: str, expires_in: int
) -> str:
    child_secret = derive_service_secret(client_id, master_secret)
    return generate_token(
        data=f"{client_id}:{data}",
        secret_key=child_secret,
        salt=salt,
        expires_in=expires_in,
    )


def verify_serve_token(token: str, master_secret: str, max_age: int = 31536000) -> str:
    """
    Verify a signed serve token and return the file ID.

    Args:
        token: The signed serve token to verify
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
    token: str, master_secret: str, salt: str, max_age: int
) -> str:
    # Decode token just to extract client_id prefix before verifying
    from app.models.client import Client

    for service in Client.all():  # or another way to get known clients
        try:
            child_secret = derive_service_secret(service.client_id, master_secret)
            raw = verify_token(token, child_secret, salt=salt, max_age=max_age)
            # Ensure the payload has the format 'client_id:asset_id'
            client_id, asset_id = raw.split(":", 1)
            if client_id == service.client_id:
                return asset_id
        except Exception:
            continue
    raise HTTPException(status_code=403, detail="Invalid or expired token")


def generate_serve_token(
    asset_id: str, client_id: str, master_secret: str, expires_in: int = 31536000
) -> str:
    """
    Generate a signed token for serving a file publicly.

    Args:
        asset_id: The file ID to generate a token for
        client_id: The service identifier
        expires_in: Number of seconds until the token expires (default: 1 year)

    Returns:
        str: The signed token for serving the file
    """
    return generate_token_with_service(
        str(asset_id), client_id, master_secret, salt="serve", expires_in=expires_in
    )
