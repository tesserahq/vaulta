from fastapi import APIRouter, UploadFile, Depends, HTTPException, Form, File, Query
from typing import Optional, List, Dict, Any
from fastapi.responses import FileResponse
from app.storage.base import StorageBackend
from app.storage.factory import StorageFactory
from app.storage.local import LocalStorageBackend
from uuid import UUID
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.document_upload import upload_document
from app.schemas.document import DocumentSearchQuery, DocumentUploadResponse, Document
from app.models.user import User
from app.services.document import DocumentService
import json
from pydantic import BaseModel

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


class DocumentLabels(BaseModel):
    """Labels for document search."""

    labels: Dict[str, Any]


class DocumentQuery(BaseModel):
    """Query parameters for document search."""

    query: DocumentLabels


@router.post("/search", response_model=List[Document])
async def get_documents_by_labels(
    query: DocumentQuery,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get documents based on query parameters.

    The request body should contain search criteria.
    Currently supported criteria:
    - query.labels: Dictionary of labels to search for. Documents must match ALL specified labels.

    Example request body:
    {
        "query": {
            "labels": {
                "status": "active",
                "type": "contract",
                "priority": "high"
            }
        }
    }

    Documents must have ALL the specified labels with matching values to be included in the results.
    """
    if not query.query.labels:
        raise HTTPException(
            status_code=400, detail="Labels must contain at least one key-value pair"
        )

    print(query.query.labels)
    document_service = DocumentService(db)
    documents = document_service.search(
        query=DocumentSearchQuery(
            labels=query.query.labels,
            skip=skip,
            limit=limit,
        )
        skip=skip,
        limit=limit,
    )

    return documents


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
    - labels: Optional JSON string containing a dictionary of labels
    
    Example using curl:
    ```bash
    curl -X POST "http://localhost:8000/documents" \
      -H "Authorization: Bearer YOUR_TOKEN" \
      -F "file=@/path/to/file.pdf" \
      -F "name=Custom Name" \
      -F "labels={\"emi\": 1234, \"hello\": \"asdf\"}"
    ```
    
    Example using Python requests:
    ```python
    import requests
    
    files = {'file': open('file.pdf', 'rb')}
    data = {
        'name': 'Custom Name',
        'labels': json.dumps({'emi': 1234, 'hello': 'asdf'})
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
    if labels:
        try:
            parsed_labels = json.loads(labels)
            if not isinstance(parsed_labels, dict):
                raise HTTPException(
                    status_code=400, detail="Labels must be a dictionary"
                )
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
