from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.document import Document
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.utils.db.filtering import apply_filters


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
        return (
            self.db.query(Document)
            .filter(Document.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

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

    def search(
        self, user_id: UUID, filters: dict, skip: int = 0, limit: int = 100
    ) -> List[Document]:
        """
        Search documents based on dynamic filter criteria.

        Args:
            user_id: The ID of the user whose documents to search
            filters: A dictionary where keys are field names and values are either:
                - A direct value (e.g. {"name": "Contract"})
                - A dictionary with 'operator' and 'value' keys (e.g. {"name": {"operator": "ilike", "value": "%contract%"}})
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List[Document]: Filtered list of documents matching the criteria
        """
        query = self.db.query(Document).filter(Document.user_id == user_id)
        query = apply_filters(query, Document, filters)
        return query.offset(skip).limit(limit).all()

    def search_by_labels(
        self, user_id: UUID, labels: List[dict], skip: int = 0, limit: int = 100
    ) -> List[Document]:
        """
        Search documents by their labels using PostgreSQL JSONB operators.
        This performs the search directly in the database for better performance.

        Args:
            user_id: The ID of the user whose documents to search
            labels: List of label dictionaries with any JSON structure (e.g. {"workspace_id": 1234})
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List[Document]: List of documents that have all the specified labels
        """
        query = self.db.query(Document).filter(Document.user_id == user_id)

        # Build the JSONB containment conditions
        for label in labels:
            # Using @> operator to check if the labels array contains the specified label
            # This is more efficient than using contains() as it uses the JSONB index
            query = query.filter(Document.labels.contains([label]))

        return query.offset(skip).limit(limit).all()

    def search_by_label_values(
        self,
        user_id: UUID,
        key: str,
        values: List[str],
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """
        Search documents by a specific label key and multiple possible values.
        This is useful for searching documents with a specific label type (e.g., all documents with status 'draft' or 'review').

        Args:
            user_id: The ID of the user whose documents to search
            key: The label key to search for
            values: List of possible values for the label
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List[Document]: List of documents that have the specified label key with any of the given values
        """
        query = self.db.query(Document).filter(Document.user_id == user_id)

        # Build the JSONB containment conditions for each value
        conditions = []
        for value in values:
            conditions.append(Document.labels.contains([{"key": key, "value": value}]))

        # Combine conditions with OR
        if conditions:
            query = query.filter(or_(*conditions))

        return query.offset(skip).limit(limit).all()
