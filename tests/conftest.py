from app.config import get_settings
import pytest
import logging
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from app.db import Base, get_db
from unittest.mock import patch
from starlette.middleware.base import BaseHTTPMiddleware
import os


# Patch authorize BEFORE importing create_app (which imports routers)
def mock_authorize(*args, **kwargs):
    """
    Mock authorize function that returns a dependency always returning True.
    This mocks tessera_sdk.server.dependencies.authorization.authorize globally.
    """

    async def always_authorized():
        return True

    return always_authorized


# Start the patch at module level before any routers are imported
_authorize_patcher = patch(
    "tessera_sdk.server.dependencies.authorization.authorize", mock_authorize
)
_authorize_patcher.start()

from app.main import create_app

pytest_plugins = [
    "tests.fixtures.user_fixtures",
    "tests.fixtures.asset_fixtures",
    "tests.fixtures.client_fixtures",
]

logger = logging.getLogger(__name__)

os.environ["ENV"] = "test"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    # Set it in the environment
    import os

    os.environ["MASTER_SECRET_KEY"] = "test"
    # Get settings with the new key
    settings = get_settings()
    yield settings


settings = get_settings()


def ensure_test_database():
    """Ensure the test database exists."""

    # Connect to default postgres database
    engine = create_engine(settings.database_url)
    conn = engine.connect()

    logger.debug(f"Connected to PostgreSQL database: {settings.database_url}")

    # Check if test database exists
    result = conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = 'vaulta_test'")
    )
    if not result.scalar():
        logger.debug("Creating test database...")
        conn.execute(text("COMMIT"))  # Close any open transaction
        conn.execute(text("CREATE DATABASE vaulta_test"))

    conn.close()
    engine.dispose()


@pytest.fixture(scope="session")
def engine():
    # Ensure test database exists
    ensure_test_database()

    # Create PostgreSQL engine for testing
    engine = create_engine(settings.database_url)

    logger.debug("Creating tables...")
    # Register models and create all tables
    Base.metadata.create_all(engine)
    logger.debug("Tables created successfully")

    yield engine

    logger.debug("Dropping tables...")
    # Drop all tables after tests
    Base.metadata.drop_all(engine)
    logger.debug("Tables dropped successfully")

    engine.dispose()


@pytest.fixture(scope="function")
def db(engine):
    # Create a new database session for each test
    connection = engine.connect()
    transaction = connection.begin()

    # bind an individual Session to the connection
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    # Clean up after each test
    session.close()

    # rollback - everything that happened with the
    # Session above (including calls to commit())
    # is rolled back.
    transaction.rollback()

    # return connection to the Engine
    connection.close()


@pytest.fixture(scope="function")
def auth_token():
    """Create a mock authorization token for testing."""
    return "mock_token"


class MockAuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Inject a fake user directly into request.state
        request.state.user = getattr(request.app.state, "test_user", None)
        return await call_next(request)


def mock_verify_token_dependency(
    request: Request,
    token: HTTPAuthorizationCredentials = None,
    db_session=None,
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
def client(db, setup_user):
    """Create a FastAPI test client with overridden database dependency and auth."""

    test_user = setup_user

    def override_get_db():
        try:
            yield db
        finally:
            pass  # Don't close the session here, it's handled by the db fixture

    # Create app with testing mode ON (no auth middleware)
    logger.debug("Creating app with testing mode ON")
    app = create_app(testing=True, auth_middleware=MockAuthenticationMiddleware)

    # Store the test user in the app state so it can be accessed by the mock dependency
    app.state.test_user = test_user

    # Override dependencies
    app.dependency_overrides[get_db] = override_get_db

    # Create test client with auth headers
    test_client = TestClient(app)

    # Add default authorization header to all requests
    test_client.headers.update({"Authorization": "Bearer mock_token"})

    yield test_client

    # Clean up
    delattr(app.state, "test_user")
    app.dependency_overrides.clear()  # Clear overrides after test
