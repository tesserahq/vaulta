class TestClientRouter:
    def test_get_clients_empty(self, client):
        """Test getting clients when none exist."""
        response = client.get("/clients")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_clients_with_data(self, client, setup_multiple_clients):
        """Test getting clients with pagination."""

        # Test default pagination
        response = client.get("/clients")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

        # Test pagination with size
        response = client.get("/clients?size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["size"] == 2

        # Test pagination with page
        response = client.get("/clients?page=2&size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["page"] == 2

    def test_create_client_success(self, client):
        """Test creating a new client successfully."""
        client_data = {"name": "New Test Client", "client_id": "new-test-client"}

        response = client.post("/clients", json=client_data)
        assert response.status_code == 200

        created_client = response.json()
        assert created_client["name"] == "New Test Client"
        assert created_client["client_id"] == "new-test-client"
        assert created_client["id"] is not None
        assert created_client["secret_generated_at"] is not None
        assert created_client["created_at"] is not None
        assert created_client["updated_at"] is not None
        assert created_client["secret"] is not None
        assert isinstance(created_client["secret"], str)
        assert len(created_client["secret"]) > 0

    def test_create_client_duplicate_client_id(self, client, setup_client):
        """Test creating a client with duplicate client_id."""
        # Try to create second client with same client_id
        client_data2 = {"name": "Second Client", "client_id": setup_client.client_id}
        response = client.post("/clients", json=client_data2)
        assert response.status_code == 400
        assert "Client ID already exists" in response.json()["detail"]

    def test_get_client_by_uuid(self, client, setup_client):
        """Test getting a client by UUID."""

        db_client = setup_client
        response = client.get(f"/clients/{db_client.id}")
        assert response.status_code == 200

        retrieved_client = response.json()
        assert retrieved_client["id"] == str(db_client.id)
        assert retrieved_client["name"] == db_client.name
        assert retrieved_client["client_id"] == db_client.client_id

    def test_get_client_by_uuid_not_found(self, client):
        """Test getting a client by UUID that doesn't exist."""
        import uuid

        fake_uuid = uuid.uuid4()

        response = client.get(f"/clients/{fake_uuid}")
        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]

    def test_get_client_by_client_id(self, client, setup_client):
        """Test getting a client by client_id (slug)."""
        db_client = setup_client
        response = client.get(f"/clients/by-client-id/{db_client.client_id}")
        assert response.status_code == 200

        retrieved_client = response.json()
        assert retrieved_client["name"] == db_client.name
        assert retrieved_client["client_id"] == db_client.client_id

    def test_get_client_by_client_id_not_found(self, client):
        """Test getting a client by client_id that doesn't exist."""
        response = client.get("/clients/by-client-id/non-existent-client")
        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]

    def test_update_client_success(self, client, setup_client):
        """Test updating a client successfully."""
        db_client = setup_client

        # Update the client
        update_data = {"name": "Updated Name"}

        response = client.put(f"/clients/{db_client.id}", json=update_data)
        assert response.status_code == 200

        updated_client = response.json()
        assert updated_client["name"] == "Updated Name"
        assert (
            updated_client["client_id"] == db_client.client_id
        )  # Should remain unchanged

    def test_update_client_not_found(self, client):
        """Test updating a client that doesn't exist."""
        import uuid

        fake_uuid = uuid.uuid4()

        update_data = {"name": "Updated Name"}
        response = client.put(f"/clients/{fake_uuid}", json=update_data)
        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]

    def test_update_client_duplicate_client_id(
        self, client, setup_client, setup_another_client
    ):
        """Test updating a client with a client_id that already exists."""
        db_client1 = setup_client
        db_client2 = setup_another_client

        # Try to update client1 with client2's client_id
        update_data = {"client_id": db_client1.client_id}
        response = client.put(f"/clients/{db_client2.id}", json=update_data)
        assert response.status_code == 400
        assert "Client ID already exists" in response.json()["detail"]

    def test_delete_client_success(self, client, setup_client):
        """Test deleting a client successfully."""
        db_client = setup_client

        response = client.delete(f"/clients/{db_client.id}")
        assert response.status_code == 200

        data = response.json()
        assert "message" in data
        assert data["message"] == "Client deleted successfully"
        assert "details" in data
        assert data["details"]["client_id"] == str(db_client.id)

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
        # Test invalid page parameter
        response = client.get("/clients?page=0")
        assert response.status_code == 422  # Validation error

        # Test invalid size parameter
        response = client.get("/clients?size=0")
        assert response.status_code == 422  # Validation error

        response = client.get("/clients?size=101")
        assert response.status_code == 422  # Validation error

    def test_regenerate_secret_success(self, client, setup_client):
        """Test regenerating a client's secret successfully."""
        db_client = setup_client

        response = client.post(f"/clients/{db_client.id}/regenerate-secret")
        assert response.status_code == 200

        regenerated_client = response.json()
        assert regenerated_client["id"] == str(db_client.id)
        assert regenerated_client["name"] == db_client.name
        assert regenerated_client["client_id"] == db_client.client_id
        assert regenerated_client["secret"] is not None
        assert isinstance(regenerated_client["secret"], str)
        assert len(regenerated_client["secret"]) > 0
        assert regenerated_client["secret_generated_at"] is not None

    def test_regenerate_secret_not_found(self, client):
        """Test regenerating secret for a client that doesn't exist."""
        import uuid

        fake_uuid = uuid.uuid4()

        response = client.post(f"/clients/{fake_uuid}/regenerate-secret")
        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]
