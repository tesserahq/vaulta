from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate, ClientWithSecret
from datetime import datetime, timezone
from app.utils.token_utils import derive_secret

from app.utils.db.filtering import apply_filters


class ClientRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_client(self, client_id: UUID) -> Optional[Client]:
        """Get a client by its UUID."""
        return self.db.query(Client).filter(Client.id == client_id).first()

    def get_client_by_client_id(self, client_id: str) -> Optional[Client]:
        """Get a client by its client_id (slug)."""
        return self.db.query(Client).filter(Client.client_id == client_id).first()

    def get_clients(self, skip: int = 0, limit: int = 100) -> List[Client]:
        """Get a list of clients with pagination."""
        return self.db.query(Client).offset(skip).limit(limit).all()

    def create_client(self, client: ClientCreate) -> ClientWithSecret:
        """Create a new client and return it with the derived secret."""
        db_client = Client(**client.model_dump())

        # Set the secret_generated_at timestamp
        db_client.secret_generated_at = datetime.now(timezone.utc)

        self.db.add(db_client)
        self.db.commit()
        self.db.refresh(db_client)

        # Generate the derived secret for this client
        derived_secret = derive_secret(db_client.client_id)

        # Create response with derived secret
        client_with_secret = ClientWithSecret(
            **db_client.__dict__, secret=derived_secret
        )

        return client_with_secret

    def update_client(self, client_id: UUID, client: ClientUpdate) -> Optional[Client]:
        """Update an existing client."""
        db_client = self.db.query(Client).filter(Client.id == client_id).first()
        if db_client:
            update_data = client.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_client, key, value)
            self.db.commit()
            self.db.refresh(db_client)
        return db_client

    def delete_client(self, client_id: UUID) -> bool:
        """Delete a client by its UUID."""
        db_client = self.db.query(Client).filter(Client.id == client_id).first()
        if db_client:
            self.db.delete(db_client)
            self.db.commit()
            return True
        return False

    def regenerate_secret(self, client_id: UUID) -> Optional[ClientWithSecret]:
        """Regenerate the secret for a client and return it with the new secret."""
        db_client = self.db.query(Client).filter(Client.id == client_id).first()
        if not db_client:
            return None

        # Update the secret_generated_at timestamp
        db_client.secret_generated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(db_client)

        # Generate the new derived secret for this client
        derived_secret = derive_secret(db_client.client_id)

        # Create response with new derived secret
        client_with_secret = ClientWithSecret(
            **db_client.__dict__, secret=derived_secret
        )

        return client_with_secret

    def search(self, filters: dict) -> List[Client]:
        """
        Search clients based on dynamic filter criteria.

        Args:
            filters: A dictionary where keys are field names and values are either:
                - A direct value (e.g. {"name": "Test Client"})
                - A dictionary with 'operator' and 'value' keys (e.g. {"name": {"operator": "ilike", "value": "%Test%"}})

        Returns:
            List[Client]: Filtered list of clients matching the criteria.
        """
        query = self.db.query(Client)
        query = apply_filters(query, Client, filters)
        return query.all()
