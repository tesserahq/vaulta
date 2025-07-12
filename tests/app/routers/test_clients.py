from app.models.client import Client


class TestClientRouter:
    def test_get_clients_empty(self, client):
        """Test getting clients when none exist."""
        response = client.get("/clients")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_clients_with_data(self, client, db):
        """Test getting clients with pagination."""
        # Create test clients
        client_data = [
            {"name": "Test Client 1", "client_id": "test-client-1"},
            {"name": "Test Client 2", "client_id": "test-client-2"},
            {"name": "Test Client 3", "client_id": "test-client-3"},
        ]

        for data in client_data:
            db_client = Client(**data)
            db.add(db_client)
        db.commit()

        # Test default pagination
        response = client.get("/clients")
        assert response.status_code == 200
        clients = response.json()
        assert len(clients) == 3

        # Test pagination with limit
        response = client.get("/clients?limit=2")
        assert response.status_code == 200
        clients = response.json()
        assert len(clients) == 2

        # Test pagination with skip
        response = client.get("/clients?skip=1&limit=2")
        assert response.status_code == 200
        clients = response.json()
        assert len(clients) == 2

    def test_create_client_success(self, client):
        """Test creating a new client successfully."""
        client_data = {"name": "New Test Client", "client_id": "new-test-client"}

        response = client.post("/clients", json=client_data)
        assert response.status_code == 200

        created_client = response.json()
        assert created_client["name"] == "New Test Client"
        assert created_client["client_id"] == "new-test-client"
        assert created_client["id"] is not None
        assert created_client["secret_generated_at"] is None
        assert created_client["created_at"] is not None
        assert created_client["updated_at"] is not None

    def test_create_client_duplicate_client_id(self, client, db):
        """Test creating a client with duplicate client_id."""
        # Create first client
        client_data = {"name": "First Client", "client_id": "duplicate-id"}
        response = client.post("/clients", json=client_data)
        assert response.status_code == 200

        # Try to create second client with same client_id
        client_data2 = {"name": "Second Client", "client_id": "duplicate-id"}
        response = client.post("/clients", json=client_data2)
        assert response.status_code == 400
        assert "Client ID already exists" in response.json()["detail"]

    def test_get_client_by_uuid(self, client, db):
        """Test getting a client by UUID."""
        # Create a test client
        client_data = {"name": "Test Client", "client_id": "test-client-uuid"}
        db_client = Client(**client_data)
        db.add(db_client)
        db.commit()
        db.refresh(db_client)

        response = client.get(f"/clients/{db_client.id}")
        assert response.status_code == 200

        retrieved_client = response.json()
        assert retrieved_client["id"] == str(db_client.id)
        assert retrieved_client["name"] == "Test Client"
        assert retrieved_client["client_id"] == "test-client-uuid"

    def test_get_client_by_uuid_not_found(self, client):
        """Test getting a client by UUID that doesn't exist."""
        import uuid

        fake_uuid = uuid.uuid4()

        response = client.get(f"/clients/{fake_uuid}")
        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]

    def test_get_client_by_client_id(self, client, db):
        """Test getting a client by client_id (slug)."""
        # Create a test client
        client_data = {"name": "Test Client", "client_id": "test-client-slug"}
        db_client = Client(**client_data)
        db.add(db_client)
        db.commit()

        response = client.get("/clients/by-client-id/test-client-slug")
        assert response.status_code == 200

        retrieved_client = response.json()
        assert retrieved_client["name"] == "Test Client"
        assert retrieved_client["client_id"] == "test-client-slug"

    def test_get_client_by_client_id_not_found(self, client):
        """Test getting a client by client_id that doesn't exist."""
        response = client.get("/clients/by-client-id/non-existent-client")
        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]

    def test_update_client_success(self, client, db):
        """Test updating a client successfully."""
        # Create a test client
        client_data = {"name": "Original Name", "client_id": "original-id"}
        db_client = Client(**client_data)
        db.add(db_client)
        db.commit()
        db.refresh(db_client)

        # Update the client
        update_data = {"name": "Updated Name"}

        response = client.put(f"/clients/{db_client.id}", json=update_data)
        assert response.status_code == 200

        updated_client = response.json()
        assert updated_client["name"] == "Updated Name"
        assert updated_client["client_id"] == "original-id"  # Should remain unchanged

    def test_update_client_not_found(self, client):
        """Test updating a client that doesn't exist."""
        import uuid

        fake_uuid = uuid.uuid4()

        update_data = {"name": "Updated Name"}
        response = client.put(f"/clients/{fake_uuid}", json=update_data)
        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]

    def test_update_client_duplicate_client_id(self, client, db):
        """Test updating a client with a client_id that already exists."""
        # Create two test clients
        client1_data = {"name": "Client 1", "client_id": "client-1"}
        client2_data = {"name": "Client 2", "client_id": "client-2"}

        db_client1 = Client(**client1_data)
        db_client2 = Client(**client2_data)
        db.add(db_client1)
        db.add(db_client2)
        db.commit()
        db.refresh(db_client1)
        db.refresh(db_client2)

        # Try to update client1 with client2's client_id
        update_data = {"client_id": "client-2"}
        response = client.put(f"/clients/{db_client1.id}", json=update_data)
        assert response.status_code == 400
        assert "Client ID already exists" in response.json()["detail"]

    def test_delete_client_success(self, client, db):
        """Test deleting a client successfully."""
        # Create a test client
        client_data = {"name": "Client to Delete", "client_id": "client-to-delete"}
        db_client = Client(**client_data)
        db.add(db_client)
        db.commit()
        db.refresh(db_client)

        response = client.delete(f"/clients/{db_client.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Client deleted successfully"

        # Verify client is deleted
        response = client.get(f"/clients/{db_client.id}")
        assert response.status_code == 404

    def test_delete_client_not_found(self, client):
        """Test deleting a client that doesn't exist."""
        import uuid

        fake_uuid = uuid.uuid4()

        response = client.delete(f"/clients/{fake_uuid}")
        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]

    def test_update_secret_timestamp_success(self, client, db):
        """Test updating the secret_generated_at timestamp."""
        # Create a test client
        client_data = {"name": "Test Client", "client_id": "test-client-secret"}
        db_client = Client(**client_data)
        db.add(db_client)
        db.commit()
        db.refresh(db_client)

        # Initially secret_generated_at should be None
        assert db_client.secret_generated_at is None

        response = client.post(f"/clients/{db_client.id}/update-secret")
        assert response.status_code == 200
        assert response.json()["message"] == "Secret timestamp updated successfully"

        # Verify the timestamp was updated
        db.refresh(db_client)
        assert db_client.secret_generated_at is not None

    def test_update_secret_timestamp_not_found(self, client):
        """Test updating secret timestamp for a client that doesn't exist."""
        import uuid

        fake_uuid = uuid.uuid4()

        response = client.post(f"/clients/{fake_uuid}/update-secret")
        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]

    def test_create_client_missing_required_fields(self, client):
        """Test creating a client with missing required fields."""
        # Missing name
        client_data = {"client_id": "test-client"}
        response = client.post("/clients", json=client_data)
        assert response.status_code == 422  # Validation error

        # Missing client_id
        client_data = {"name": "Test Client"}
        response = client.post("/clients", json=client_data)
        assert response.status_code == 422  # Validation error

    def test_pagination_parameters(self, client):
        """Test pagination parameter validation."""
        # Test invalid skip parameter
        response = client.get("/clients?skip=-1")
        assert response.status_code == 422  # Validation error

        # Test invalid limit parameter
        response = client.get("/clients?limit=0")
        assert response.status_code == 422  # Validation error

        response = client.get("/clients?limit=1001")
        assert response.status_code == 422  # Validation error
