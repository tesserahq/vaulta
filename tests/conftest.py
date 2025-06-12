from app.config import get_settings
import pytest
import logging
from fastapi.testclient import TestClient
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from app.main import create_app
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    settings = get_settings()
    yield settings


@pytest.fixture(scope="function")
def auth_token():
    """Create a mock authorization token for testing."""
    return "mock_token"


class MockAuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        return await call_next(request)


def mock_verify_token_dependency(
    request: Request,
    token: HTTPAuthorizationCredentials = None,
):
    """Mock the verify_token_dependency to bypass JWT verification."""
    # Get the test user from the app state
    user = getattr(request.app.state, "test_user", None)
    logger.debug(f"mock_verify_token_dependency: {user}")
    if user is None:
        raise Exception("Test user not found in app state")
    request.state.user = user

    return user


@pytest.fixture(scope="function")
def client():
    """Create a FastAPI test client with overridden database dependency and auth."""

    # Create app with testing mode ON (no auth middleware)
    logger.debug("Creating app with testing mode ON")
    app = create_app(testing=True, auth_middleware=MockAuthenticationMiddleware)

    # Create test client with auth headers
    test_client = TestClient(app)

    # Add default authorization header to all requests
    test_client.headers.update({"Authorization": "Bearer mock_token"})

    yield test_client

    # Clean up
    app.dependency_overrides.clear()  # Clear overrides after test
