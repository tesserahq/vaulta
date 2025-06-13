from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.document import Document
from app.schemas.document import DocumentCreate, DocumentUpdate, DocumentSearchQuery


class DocumentService:
    def __init__(self, db: Session):
        self.db = db

    def get_document(self, document_id: UUID) -> Optional[Document]:
        """Get a document by its ID."""
        return self.db.query(Document).filter(Document.id == document_id).first()

    def get_user_documents(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Document]:
        """Get all documents for a specific user."""
        query = DocumentSearchQuery(user_id=user_id, skip=skip, limit=limit)
        return self.search(query)

    def create_document(self, document: DocumentCreate, user_id: UUID) -> Document:
        """Create a new document."""
        db_document = Document(**document.model_dump(), user_id=user_id)
        self.db.add(db_document)
        self.db.commit()
        self.db.refresh(db_document)
        return db_document

    def update_document(
        self, document_id: UUID, document: DocumentUpdate
    ) -> Optional[Document]:
        """Update an existing document."""
        db_document = self.db.query(Document).filter(Document.id == document_id).first()
        if db_document:
            update_data = document.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_document, key, value)
            self.db.commit()
            self.db.refresh(db_document)
        return db_document

    def delete_document(self, document_id: UUID) -> bool:
        """Delete a document."""
        db_document = self.db.query(Document).filter(Document.id == document_id).first()
        if db_document:
            self.db.delete(db_document)
            self.db.commit()
            return True
        return False

    def search(self, query: DocumentSearchQuery) -> List[Document]:
        """
        Search documents by user_id, labels, and/or state.

        Args:
            query: DocumentSearchQuery object containing search parameters
                - user_id: Optional UUID to filter by document owner
                - labels: Optional dictionary of labels to match
                - state: Optional state to filter by
                - skip: Number of records to skip (for pagination)
                - limit: Maximum number of records to return

        Returns:
            List[Document]: List of documents matching the search criteria
        """
        db_query = self.db.query(Document)

        # Apply user_id filter if provided
        if query.user_id:
            db_query = db_query.filter(Document.user_id == query.user_id)

        # Apply labels filter if provided
        if query.labels:
            db_query = db_query.filter(Document.labels.op("@>")(query.labels))

        # Apply state filter if provided
        if query.state:
            db_query = db_query.filter(Document.state == query.state)

        return db_query.offset(query.skip).limit(query.limit).all()
