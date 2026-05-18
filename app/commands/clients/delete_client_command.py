import logging

from sqlalchemy.orm import Session

from app.exceptions.resource_not_found_error import ResourceNotFoundError
from app.models.client import Client
from app.repositories.client_repository import ClientRepository


class DeleteClientCommand:
    def __init__(self, db: Session):
        self.db = db
        self.client_repository = ClientRepository(db)
        self.logger = logging.getLogger(__name__)

    def execute(self, record: Client) -> None:
        try:
            if not self.client_repository.delete_client(record.id):
                raise ResourceNotFoundError("Client not found")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to delete client: {str(e)}")
