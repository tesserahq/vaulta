import logging

from sqlalchemy.orm import Session

from app.repositories.client_repository import ClientRepository
from app.schemas.client import ClientCreate, ClientWithSecret


class CreateClientCommand:
    def __init__(self, db: Session):
        self.db = db
        self.client_repository = ClientRepository(db)
        self.logger = logging.getLogger(__name__)

    def execute(self, data: ClientCreate) -> ClientWithSecret:
        try:
            if self.client_repository.get_client_by_client_id(data.client_id):
                raise ValueError("Client ID already exists")
            return self.client_repository.create_client(data)
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create client: {str(e)}")
