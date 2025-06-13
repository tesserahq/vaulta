from fastapi import APIRouter, UploadFile, Depends, HTTPException, Form, File
from typing import Optional, List
from fastapi.responses import FileResponse
from app.storage.base import StorageBackend
from app.storage.factory import StorageFactory
from app.storage.local import LocalStorageBackend
from uuid import UUID
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.document_upload import upload_document
from app.schemas.document import DocumentUploadResponse, Label
from app.models.user import User
from app.services.document import DocumentService
import json

from app.utils.auth import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])


def get_storage_backend() -> StorageBackend:
    """Get the configured storage backend."""
    return StorageFactory.get_backend()


@router.get("/download/{token}")
async def download_document(
    token: str,
    storage: StorageBackend = Depends(get_storage_backend),
    db: Session = Depends(get_db),
):
    """Download a private file using a signed token."""
    if not isinstance(storage, LocalStorageBackend):
        raise HTTPException(
            status_code=400,
            detail="Token-based downloads are only supported with local storage",
        )

    try:
        # Verify the token and get the document ID
        document_id = storage.verify_token(token)

        document_service = DocumentService(db)
        document = document_service.get_document(UUID(document_id))

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get the file path
        file_path = storage.private_dir / document_id

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            file_path,
            media_type=str(document.mime_type),
            filename=str(document.filename),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid document ID: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")


@router.post("", response_model=DocumentUploadResponse)
async def upload_document_endpoint(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    labels: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a document with optional name and labels.
    
    This endpoint accepts multipart form data with the following fields:
    - file: The file to upload (required)
    - name: Optional custom name for the document
    - labels: Optional JSON string containing an array of label objects
    
    Example using curl:
    ```bash
    curl -X POST "http://localhost:8000/documents" \
      -H "Authorization: Bearer YOUR_TOKEN" \
      -F "file=@/path/to/file.pdf" \
      -F "name=Custom Name" \
      -F "labels=[{\"key\":\"type\",\"value\":\"contract\"}]"
    ```
    
    Example using Python requests:
    ```python
    import requests
    
    files = {'file': open('file.pdf', 'rb')}
    data = {
        'name': 'Custom Name',
        'labels': json.dumps([{'key': 'type', 'value': 'contract'}])
    }
    
    response = requests.post(
        'http://localhost:8000/documents',
        headers={'Authorization': f'Bearer {token}'},
        files=files,
        data=data
    )
    ```
    """
    # Parse labels from JSON string if provided
    parsed_labels = None
    print("labels", labels)
    if labels:
        try:
            labels_data = json.loads(labels)
            parsed_labels = [Label(**label) for label in labels_data]
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid labels format")
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Error parsing labels: {str(e)}"
            )

    document_service = DocumentService(db)
    storage = StorageFactory.get_backend()
    return await upload_document(
        file=file,
        user_id=UUID(str(current_user.id)),
        document_service=document_service,
        storage=storage,
        name=name,
        labels=parsed_labels,
    )
