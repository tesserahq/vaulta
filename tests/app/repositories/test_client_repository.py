from app.repositories.client_repository import ClientRepository
from app.schemas.client import ClientCreate, ClientUpdate


class TestClientRepository:
    def test_create_client(self, db):
        """Test creating a new client."""
        repository = ClientRepository(db)
        client_data = ClientCreate(name="Test Client", client_id="test-client-123")

        client = repository.create_client(client_data)

        assert client.id is not None
        assert client.name == "Test Client"
        assert client.client_id == "test-client-123"
        assert client.secret_generated_at is not None
        assert client.created_at is not None
        assert client.updated_at is not None
        assert client.secret is not None
        assert isinstance(client.secret, str)
        assert len(client.secret) > 0

    def test_get_client(self, db):
        """Test getting a client by UUID."""
        repository = ClientRepository(db)
        client_data = ClientCreate(name="Test Client", client_id="test-client-456")

        created_client = repository.create_client(client_data)
        retrieved_client = repository.get_client(created_client.id)

        assert retrieved_client is not None
        assert retrieved_client.id == created_client.id
        assert retrieved_client.name == "Test Client"

    def test_get_client_by_client_id(self, db):
        """Test getting a client by client_id (slug)."""
        repository = ClientRepository(db)
        client_data = ClientCreate(name="Test Client", client_id="test-client-789")

        created_client = repository.create_client(client_data)
        retrieved_client = repository.get_client_by_client_id("test-client-789")

        assert retrieved_client is not None
        assert retrieved_client.id == created_client.id
        assert retrieved_client.client_id == "test-client-789"

    def test_update_client(self, db):
        """Test updating a client."""
        repository = ClientRepository(db)
        client_data = ClientCreate(name="Original Name", client_id="original-id")

        created_client = repository.create_client(client_data)

        update_data = ClientUpdate(name="Updated Name")
        updated_client = repository.update_client(created_client.id, update_data)

        assert updated_client is not None
        assert updated_client.name == "Updated Name"
        assert updated_client.client_id == "original-id"  # Should remain unchanged

    def test_delete_client(self, db):
        """Test deleting a client."""
        repository = ClientRepository(db)
        client_data = ClientCreate(name="Test Client", client_id="test-client-delete")

        created_client = repository.create_client(client_data)
        success = repository.delete_client(created_client.id)

        assert success is True

        # Verify client is deleted
        retrieved_client = repository.get_client(created_client.id)
        assert retrieved_client is None

    def test_regenerate_secret(self, db):
        """Test regenerating a client's secret."""
        repository = ClientRepository(db)
        client_data = ClientCreate(
            name="Test Client", client_id="test-client-regenerate"
        )

        # Create a client
        created_client = repository.create_client(client_data)
        original_secret = created_client.secret
        original_timestamp = created_client.secret_generated_at

        # Regenerate the secret
        regenerated_client = repository.regenerate_secret(created_client.id)

        assert regenerated_client is not None
        assert regenerated_client.id == created_client.id
        assert regenerated_client.secret is not None
        assert isinstance(regenerated_client.secret, str)
        assert len(regenerated_client.secret) > 0
        assert regenerated_client.secret_generated_at is not None
        assert regenerated_client.secret_generated_at > original_timestamp

    def test_regenerate_secret_client_not_found(self, db):
        """Test regenerating secret for a non-existent client."""
        repository = ClientRepository(db)
        import uuid

        fake_uuid = uuid.uuid4()
        result = repository.regenerate_secret(fake_uuid)

        assert result is None

    def test_get_clients_with_pagination(self, db):
        """Test getting clients with pagination."""
        repository = ClientRepository(db)

        # Create multiple clients
        for i in range(5):
            client_data = ClientCreate(
                name=f"Test Client {i}", client_id=f"test-client-{i}"
            )
            repository.create_client(client_data)

        # Test pagination
        clients = repository.get_clients(skip=0, limit=3)
        assert len(clients) == 3

        clients = repository.get_clients(skip=3, limit=3)
        assert len(clients) == 2  # Only 2 remaining clients
