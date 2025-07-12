import pytest
from app.models.client import Client


@pytest.fixture(scope="function")
def test_client(db, faker):
    """Create a test client for use in tests."""
    client_data = {
        "name": faker.company(),
        "client_id": faker.slug(),
    }

    client = Client(**client_data)
    db.add(client)
    db.commit()
    db.refresh(client)

    return client


@pytest.fixture(scope="function")
def setup_client(db, faker):
    """Create a test client for use in tests."""
    client_data = {
        "name": faker.company(),
        "client_id": faker.slug(),
    }

    client = Client(**client_data)
    db.add(client)
    db.commit()
    db.refresh(client)

    return client


@pytest.fixture(scope="function")
def setup_another_client(db, faker):
    """Create a test client for use in tests."""
    client_data = {
        "name": faker.company(),
        "client_id": faker.slug(),
    }

    another_client = Client(**client_data)
    db.add(another_client)
    db.commit()
    db.refresh(another_client)

    return another_client


@pytest.fixture(scope="function")
def setup_multiple_clients(db, faker):
    """Create multiple test clients for use in tests."""
    clients = []
    for i in range(3):
        client_data = {
            "name": f"Test Client {i}",
            "client_id": f"test-client-{i}",
        }
        client = Client(**client_data)
        db.add(client)
        clients.append(client)

    db.commit()
    for client in clients:
        db.refresh(client)

    return clients
