import pytest
from uuid import uuid4
from datetime import datetime, timezone
from app.services.client_service import ClientService
from app.schemas.client import ClientCreate, ClientUpdate


class TestClientService:
    def test_create_client(self, db):
        """Test creating a new client."""
        service = ClientService(db)
        client_data = ClientCreate(name="Test Client", client_id="test-client-123")

        client = service.create_client(client_data)

        assert client.id is not None
        assert client.name == "Test Client"
        assert client.client_id == "test-client-123"
        assert client.secret_generated_at is None
        assert client.created_at is not None
        assert client.updated_at is not None

    def test_get_client(self, db):
        """Test getting a client by UUID."""
        service = ClientService(db)
        client_data = ClientCreate(name="Test Client", client_id="test-client-456")

        created_client = service.create_client(client_data)
        retrieved_client = service.get_client(created_client.id)

        assert retrieved_client is not None
        assert retrieved_client.id == created_client.id
        assert retrieved_client.name == "Test Client"

    def test_get_client_by_client_id(self, db):
        """Test getting a client by client_id (slug)."""
        service = ClientService(db)
        client_data = ClientCreate(name="Test Client", client_id="test-client-789")

        created_client = service.create_client(client_data)
        retrieved_client = service.get_client_by_client_id("test-client-789")

        assert retrieved_client is not None
        assert retrieved_client.id == created_client.id
        assert retrieved_client.client_id == "test-client-789"

    def test_update_client(self, db):
        """Test updating a client."""
        service = ClientService(db)
        client_data = ClientCreate(name="Original Name", client_id="original-id")

        created_client = service.create_client(client_data)

        update_data = ClientUpdate(name="Updated Name")
        updated_client = service.update_client(created_client.id, update_data)

        assert updated_client is not None
        assert updated_client.name == "Updated Name"
        assert updated_client.client_id == "original-id"  # Should remain unchanged

    def test_delete_client(self, db):
        """Test deleting a client."""
        service = ClientService(db)
        client_data = ClientCreate(name="Test Client", client_id="test-client-delete")

        created_client = service.create_client(client_data)
        success = service.delete_client(created_client.id)

        assert success is True

        # Verify client is deleted
        retrieved_client = service.get_client(created_client.id)
        assert retrieved_client is None

    def test_update_secret_generated_at(self, db):
        """Test updating the secret_generated_at timestamp."""
        service = ClientService(db)
        client_data = ClientCreate(name="Test Client", client_id="test-client-secret")

        created_client = service.create_client(client_data)
        assert created_client.secret_generated_at is None

        updated_client = service.update_secret_generated_at(created_client.id)

        assert updated_client is not None
        assert updated_client.secret_generated_at is not None
        assert isinstance(updated_client.secret_generated_at, datetime)

    def test_get_clients_with_pagination(self, db):
        """Test getting clients with pagination."""
        service = ClientService(db)

        # Create multiple clients
        for i in range(5):
            client_data = ClientCreate(
                name=f"Test Client {i}", client_id=f"test-client-{i}"
            )
            service.create_client(client_data)

        # Test pagination
        clients = service.get_clients(skip=0, limit=3)
        assert len(clients) == 3

        clients = service.get_clients(skip=3, limit=3)
        assert len(clients) == 2  # Only 2 remaining clients
