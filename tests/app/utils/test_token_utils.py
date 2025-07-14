import pytest
from fastapi import HTTPException
from app.utils.token_utils import (
    derive_secret,
    generate_token_with_client,
    verify_token_with_derived_secret,
    sign_serve_url,
    verify_signed_url,
)


class TestTokenUtils:
    def test_derive_secret(self):
        """Test deriving a secret from client_id and master_secret."""
        client_id = "test-client-123"
        master_secret = "test-master-secret"

        secret = derive_secret(client_id, master_secret)

        assert secret is not None
        assert isinstance(secret, str)
        assert len(secret) > 0

        # Same inputs should produce same output
        secret2 = derive_secret(client_id, master_secret)
        assert secret == secret2

        # Different inputs should produce different outputs
        secret3 = derive_secret("different-client", master_secret)
        assert secret != secret3

    def test_derive_secret_without_master_secret(self):
        """Test deriving a secret without providing master_secret (uses config)."""
        client_id = "test-client-config"

        secret = derive_secret(client_id)

        assert secret is not None
        assert isinstance(secret, str)
        assert len(secret) > 0

    def test_generate_and_verify_token_with_derived_secret(self):
        """Test generating and verifying a token using derived secret."""
        client_id = "test-client-token"
        master_secret = "test-master-secret"
        asset_id = "test-asset-123"
        salt = "test-salt"
        expires_in = 3600

        # Generate derived secret
        derived_secret = derive_secret(client_id, master_secret)

        # Generate token
        token = generate_token_with_client(
            data=asset_id,
            client_id=client_id,
            master_secret=master_secret,
            salt=salt,
            expires_in=expires_in,
        )

        # Verify token with derived secret
        verified_asset_id = verify_token_with_derived_secret(
            token=token, derived_secret=derived_secret, salt=salt, max_age=expires_in
        )

        assert verified_asset_id == asset_id

    def test_verify_token_with_derived_secret_invalid_token(self):
        """Test verifying an invalid token with derived secret."""
        derived_secret = derive_secret("test-client", "test-master-secret")

        with pytest.raises(HTTPException) as exc_info:
            verify_token_with_derived_secret(
                token="invalid-token", derived_secret=derived_secret, salt="test-salt"
            )

        assert exc_info.value.status_code == 403
        assert "Invalid or expired token" in exc_info.value.detail

    def test_verify_token_with_derived_secret_wrong_secret(self):
        """Test verifying a token with wrong derived secret."""
        client_id = "test-client"
        master_secret = "test-master-secret"
        asset_id = "test-asset"
        salt = "test-salt"

        # Generate token with one secret
        token = generate_token_with_client(
            data=asset_id, client_id=client_id, master_secret=master_secret, salt=salt
        )

        # Try to verify with different secret
        wrong_secret = derive_secret("different-client", "different-master")

        with pytest.raises(HTTPException) as exc_info:
            verify_token_with_derived_secret(
                token=token, derived_secret=wrong_secret, salt=salt
            )

        assert exc_info.value.status_code == 403
        assert "Invalid or expired token" in exc_info.value.detail

    def test_verify_token_with_derived_secret_wrong_salt(self):
        """Test verifying a token with wrong salt."""
        client_id = "test-client"
        master_secret = "test-master-secret"
        asset_id = "test-asset"
        salt = "test-salt"

        # Generate token
        token = generate_token_with_client(
            data=asset_id, client_id=client_id, master_secret=master_secret, salt=salt
        )

        # Generate derived secret
        derived_secret = derive_secret(client_id, master_secret)

        # Try to verify with wrong salt
        with pytest.raises(HTTPException) as exc_info:
            verify_token_with_derived_secret(
                token=token, derived_secret=derived_secret, salt="wrong-salt"
            )

        assert exc_info.value.status_code == 403
        assert "Invalid or expired token" in exc_info.value.detail

    def test_token_expiration(self):
        """Test that tokens expire correctly."""
        client_id = "test-client-expire"
        master_secret = "test-master-secret"
        asset_id = "test-asset-expire"
        salt = "test-salt"
        expires_in = 1  # 1 second expiration

        # Generate derived secret
        derived_secret = derive_secret(client_id, master_secret)

        # Generate token with short expiration
        token = generate_token_with_client(
            data=asset_id,
            client_id=client_id,
            master_secret=master_secret,
            salt=salt,
            expires_in=expires_in,
        )

        # Verify token immediately (should work)
        verified_asset_id = verify_token_with_derived_secret(
            token=token, derived_secret=derived_secret, salt=salt, max_age=expires_in
        )
        assert verified_asset_id == asset_id

        # Wait for token to expire and verify it fails
        import time

        time.sleep(2)  # Wait longer than expiration time

        with pytest.raises(HTTPException) as exc_info:
            verify_token_with_derived_secret(
                token=token,
                derived_secret=derived_secret,
                salt=salt,
                max_age=expires_in,
            )

        assert exc_info.value.status_code == 403
        assert "Invalid or expired token" in exc_info.value.detail

    def test_verify_signed_url_expired(self):
        """Test that an expired signed URL is rejected."""
        document_id = "doc-expired"
        client_id = "test-client"
        secret = "super-secret-key"
        expires_in = 1  # 1 second

        url = sign_serve_url(document_id, client_id, expires_in, secret)
        payload = url[7:]  # Remove "/serve/" prefix
        import time

        time.sleep(2)  # Wait for expiration
        with pytest.raises(HTTPException) as exc_info:
            verify_signed_url(payload, secret)
        assert exc_info.value.status_code == 403
        assert "expired" in exc_info.value.detail

    def test_verify_signed_url_invalid_signature(self):
        """Test that a tampered signature is rejected."""
        document_id = "doc-tamper"
        client_id = "test-client"
        secret = "super-secret-key"
        expires_in = 10

        url = sign_serve_url(document_id, client_id, expires_in, secret)
        payload = url[7:]  # Remove "/serve/" prefix
        # Tamper with the signature
        tampered_payload = payload[:-1] + ("0" if payload[-1] != "0" else "1")
        with pytest.raises(HTTPException) as exc_info:
            verify_signed_url(tampered_payload, secret)
        assert exc_info.value.status_code == 403
        assert "Invalid signature" in exc_info.value.detail

    def test_verify_signed_url_invalid_format(self):
        """Test that an invalid URL format is rejected."""
        secret = "super-secret-key"
        # Not enough parts
        with pytest.raises(HTTPException) as exc_info:
            verify_signed_url("onlyonepart", secret)
        assert exc_info.value.status_code == 400
        # Non-integer expires_at
        with pytest.raises(HTTPException) as exc_info:
            verify_signed_url("doc.client.notanint.sig", secret)
        assert exc_info.value.status_code == 400
