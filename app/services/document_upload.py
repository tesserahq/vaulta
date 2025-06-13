from typing import Optional
from uuid import UUID
from fastapi import UploadFile
from app.services.document import DocumentService
from app.schemas.document import (
    DocumentCreate,
    DocumentUpdate,
    Label,
    DocumentUploadResponse,
)
from app.storage.base import StorageBackend
from app.constants.document import DocumentState


async def upload_document(
    file: UploadFile,
    user_id: UUID,
    document_service: DocumentService,
    storage: StorageBackend,
    name: Optional[str] = None,
    labels: Optional[list[Label]] = None,
) -> DocumentUploadResponse:
    """
    Upload a file and create a document record.

    Args:
        file: The file to upload
        user_id: The ID of the user uploading the file
        document_service: DocumentService instance
        storage: StorageBackend instance
        name: Optional custom name for the document (defaults to original filename)
        labels: Optional list of labels to attach to the document

    Returns:
        DocumentUploadResponse: Document information including ID and URL
    """
    # Get file metadata
    file_size = 0
    file.file.seek(0, 2)  # Seek to end of file
    file_size = file.file.tell()
    file.file.seek(0)  # Reset file pointer

    # Create document record in pending state
    document_data = DocumentCreate(
        name=name or file.filename,
        filename=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        size=file_size,
        labels=labels or [],
        state=DocumentState.PENDING.value,
        state_message="Document record created, waiting for upload",
    )

    # Save document to database
    document = document_service.create_document(document_data, user_id)

    try:
        # Update state to uploading
        document_service.update_document(
            document.id,
            DocumentUpdate(
                state=DocumentState.UPLOADING.value,
                state_message="File upload in progress",
            ),
        )

        # Save file to storage
        await storage.save(document.id, file)

        # Get URL for accessing the file
        url = await storage.get_url(document.id)

        # Update state to completed
        document_service.update_document(
            document.id,
            DocumentUpdate(
                state=DocumentState.COMPLETED.value,
                state_message="File upload completed successfully",
            ),
        )

        return DocumentUploadResponse(
            document_id=document.id,
            url=url,
            name=document.name,
            filename=document.filename,
            mime_type=document.mime_type,
            size=document.size,
            human_readable_size=document.human_readable_size,
            labels=document.labels,
            state=DocumentState.COMPLETED.value,
            state_message="File upload completed successfully",
        )

    except Exception as e:
        # Update state to failed
        document_service.update_document(
            document.id,
            DocumentUpdate(
                state=DocumentState.FAILED.value,
                state_message=f"Upload failed: {str(e)}",
            ),
        )
        raise
