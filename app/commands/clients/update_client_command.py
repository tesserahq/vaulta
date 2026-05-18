import logging

from sqlalchemy.orm import Session

from app.exceptions.resource_not_found_error import ResourceNotFoundError
from app.models.client import Client
from app.repositories.client_repository import ClientRepository
from app.schemas.client import Client as ClientResponse
from app.schemas.client import ClientUpdate


class UpdateClientCommand:
    def __init__(self, db: Session):
        self.db = db
        self.client_repository = ClientRepository(db)
        self.logger = logging.getLogger(__name__)

    def execute(self, record: Client, data: ClientUpdate) -> ClientResponse:
        try:
            if data.client_id and data.client_id != record.client_id:
                if self.client_repository.get_client_by_client_id(data.client_id):
                    raise ValueError("Client ID already exists")
            updated = self.client_repository.update_client(record.id, data)
            if not updated:
                raise ResourceNotFoundError("Client not found")
            return ClientResponse.model_validate(updated)
        except (ValueError, ResourceNotFoundError):
            raise
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to update client: {str(e)}")
