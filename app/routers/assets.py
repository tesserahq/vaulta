from fastapi import APIRouter, UploadFile, Depends, HTTPException, Form, File, Query
from typing import Optional, List, Dict, Any
from fastapi.responses import FileResponse
from app.storage.base import StorageBackend
from app.storage.factory import StorageFactory
from app.storage.local import LocalStorageBackend
from uuid import UUID
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.asset_upload import upload_asset
from app.schemas.asset import AssetSearchQuery, AssetUploadResponse, Asset
from app.models.user import User
from app.services.asset_service import AssetService
import json
from pydantic import BaseModel
import os
from datetime import datetime

from app.utils.auth import get_current_user

router = APIRouter(prefix="/assets", tags=["assets"])


def get_storage_backend() -> StorageBackend:
    """Get the configured storage backend."""
    return StorageFactory.get_backend()


@router.get("/serve/{token}")
async def serve_document_via_token(
    token: str,
    storage: StorageBackend = Depends(get_storage_backend),
    db: Session = Depends(get_db),
):
    """Serve a file via token for public access (like S3 pre-signed URLs)."""
    if not isinstance(storage, LocalStorageBackend):
        raise HTTPException(
            status_code=400,
            detail="Token-based serving is only supported with local storage",
        )

    try:
        # Verify the token and get the file ID
        asset_id = storage.verify_serve_token(token)

        asset_service = AssetService(db)
        asset = asset_service.get_asset(UUID(asset_id))

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # Get the file path
        file_path = storage.private_dir / asset_id

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Asset not found")

        # Get file metadata for headers
        stat_info = os.stat(file_path)
        last_modified = datetime.fromtimestamp(stat_info.st_mtime)

        # Generate ETag based on file size and modification time
        etag = f'"{stat_info.st_size}-{int(stat_info.st_mtime)}"'

        return FileResponse(
            file_path,
            media_type=str(asset.mime_type),
            filename=str(asset.filename),
            headers={
                "Content-Disposition": f"inline; filename={asset.filename}",
                "Cache-Control": "public, max-age=31536000, immutable",
                "ETag": etag,
                "Last-Modified": last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid asset ID: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving asset: {str(e)}")


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
        # Verify the token and get the file ID
        asset_id = storage.verify_token(token)

        asset_service = AssetService(db)
        asset = asset_service.get_asset(UUID(asset_id))

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # Get the file path
        file_path = storage.private_dir / asset_id

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Asset not found")

        return FileResponse(
            file_path,
            media_type=str(asset.mime_type),
            filename=str(asset.filename),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid asset ID: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error downloading asset: {str(e)}"
        )


class DocumentLabels(BaseModel):
    """Labels for asset search."""

    labels: Dict[str, Any]


class DocumentQuery(BaseModel):
    """Query parameters for asset search."""

    query: DocumentLabels


@router.post("/search", response_model=List[Asset])
async def get_assets_by_labels(
    query: DocumentQuery,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get assets based on query parameters.

    The request body should contain search criteria.
    Currently supported criteria:
    - query.labels: Dictionary of labels to search for. Assets must match ALL specified labels.

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

    Assets must have ALL the specified labels with matching values to be included in the results.
    """
    if not query.query.labels:
        raise HTTPException(
            status_code=400, detail="Labels must contain at least one key-value pair"
        )

    asset_service = AssetService(db)
    assets = asset_service.search(
        query=AssetSearchQuery(labels=query.query.labels, skip=skip, limit=limit)
    )

    return assets


@router.post("", response_model=AssetUploadResponse)
async def upload_asset_endpoint(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    labels: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an asset with optional name and labels.
    
    This endpoint accepts multipart form data with the following fields:
    - file: The asset to upload (required)
    - name: Optional custom name for the asset
    - labels: Optional JSON string containing a dictionary of labels
    
    Example using curl:
    ```bash
    curl -X POST "http://localhost:8000/assets" \
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
        'http://localhost:8000/assets',
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

    asset_service = AssetService(db)
    storage = StorageFactory.get_backend()
    return await upload_asset(
        file=file,
        user_id=UUID(str(current_user.id)),
        asset_service=asset_service,
        storage=storage,
        name=name,
        labels=parsed_labels,
    )
