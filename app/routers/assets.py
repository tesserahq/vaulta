from fastapi import APIRouter, UploadFile, Depends, HTTPException, Form, Query
from typing import Optional, List, Dict, Any
from fastapi.responses import FileResponse, StreamingResponse
from app.storage.base import StorageBackend
from app.storage.factory import StorageFactory
from app.storage.local import LocalStorageBackend
from uuid import UUID
from sqlalchemy.orm import Session
from app.cache.asset_cache import AssetCache
from app.commands.assets.delete_asset_command import DeleteAssetCommand
from app.db import get_db
from app.services.asset_lookup import get_asset_for_serving
from app.services.asset_upload import upload_asset
from app.schemas.asset import AssetSearchQuery, AssetUploadResponse, Asset
from app.schemas.common import MessageResponse
from app.models.user import User
from app.repositories.asset_repository import AssetRepository
import json
from pydantic import BaseModel, Field
import os
from datetime import datetime
import httpx
import tempfile
from urllib.parse import urlparse

from app.utils.auth import get_current_user
from app.utils.token_utils import verify_signed_url
from app.providers import AnalysisProvider
from app.routers.utils.dependencies import (
    get_asset_by_id,
    get_asset_cache,
    get_validated_file,
    resolve_analysis_config,
)
from app.services.processors.analysis import AnalysisProcessor
from app.services.processors.base import ProcessorContext
from app.services.processors.modela import (
    ModelaAnalysisProcessor,
    ModelaSummarizationProcessor,
)
from app.services.processors.summarization import SummarizationProcessor
from app.services.summarization.claude import ClaudeSummarizationService

router = APIRouter(prefix="/assets", tags=["assets"])


def get_storage_backend() -> StorageBackend:
    """Get the configured storage backend."""
    return StorageFactory.get_backend()


@router.get("", response_model=List[Asset])
async def get_all_assets(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all assets with pagination support.

    Returns a paginated list of all assets in the system.
    Use skip and limit parameters for pagination.
    """
    asset_repository = AssetRepository(db)
    assets = asset_repository.search(query=AssetSearchQuery(skip=skip, limit=limit))

    return assets


@router.get("/{asset_id}", response_model=Asset)
async def get_asset(
    asset: Asset = Depends(get_asset_by_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific asset by UUID."""
    return asset


@router.get("/serve/{payload}")
async def serve_asset_via_signed_url(
    payload: str,
    storage: StorageBackend = Depends(get_storage_backend),
    db: Session = Depends(get_db),
    cache: AssetCache = Depends(get_asset_cache),
):
    """Serve a file via signed URL payload for public access."""
    try:
        # Verify the signed URL payload and get the asset ID
        asset_id = verify_signed_url(payload)

        try:
            asset_uuid = UUID(asset_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Asset not found")

        asset_repository = AssetRepository(db)
        metadata = get_asset_for_serving(asset_uuid, asset_repository, cache)

        # Release the DB connection now: FastAPI doesn't close `Depends(get_db)`
        # sessions until the full response (including a StreamingResponse body)
        # has been sent, so without this the connection would sit checked out
        # of the pool for the entire file transfer/S3 fetch instead of just
        # this lookup.
        db.close()

        if metadata is None:
            raise HTTPException(status_code=404, detail="Asset not found")

        if isinstance(storage, LocalStorageBackend):
            file_path = storage.private_dir / asset_id

            if not file_path.exists():
                raise HTTPException(status_code=404, detail="Asset not found")

            stat_info = os.stat(file_path)
            last_modified = datetime.fromtimestamp(stat_info.st_mtime)
            etag = f'"{stat_info.st_size}-{int(stat_info.st_mtime)}"'

            return FileResponse(
                file_path,
                media_type=metadata.mime_type,
                filename=metadata.filename,
                headers={
                    "Content-Disposition": f"inline; filename={metadata.filename}",
                    "Cache-Control": "public, max-age=31536000, immutable",
                    "ETag": etag,
                    "Last-Modified": last_modified.strftime(
                        "%a, %d %b %Y %H:%M:%S GMT"
                    ),
                },
            )

        # For S3 and other backends: proxy the bytes through the server.
        # This avoids exposing presigned URLs to clients and works with existing /serve/ tokens.
        presigned_url = await storage.get_url(asset_id)

        async def stream_from_s3():
            async with httpx.AsyncClient() as s3_client:
                async with s3_client.stream("GET", presigned_url) as s3_response:
                    async for chunk in s3_response.aiter_bytes(chunk_size=65536):
                        yield chunk

        return StreamingResponse(
            stream_from_s3(),
            media_type=metadata.mime_type,
            headers={
                "Content-Disposition": f"inline; filename={metadata.filename}",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving asset: {str(e)}")


@router.get("/download/{token}")
async def download_asset(
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

        asset_repository = AssetRepository(db)
        asset = asset_repository.get_asset(UUID(asset_id))

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


class AssetLabels(BaseModel):
    """Labels for asset search."""

    labels: Dict[str, Any]


class AssetQuery(BaseModel):
    """Query parameters for asset search."""

    query: AssetLabels


@router.post("/search", response_model=List[Asset])
async def get_assets_by_labels(
    query: AssetQuery,
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

    asset_repository = AssetRepository(db)
    assets = asset_repository.search(
        query=AssetSearchQuery(labels=query.query.labels, skip=skip, limit=limit)
    )

    return assets


@router.post("", response_model=AssetUploadResponse)
async def upload_asset_endpoint(
    file: UploadFile = Depends(get_validated_file),
    name: Optional[str] = Form(None),
    labels: Optional[str] = Form(None),
    extract_data: bool = Form(False),
    config_id: Optional[UUID] = Form(None),
    summarize: bool = Form(False),
    project_id: Optional[str] = Form(None),
    expires_in: Optional[int] = Form(
        None,
        description=(
            "Optional: request a long-lived signed serve_url (seconds), "
            "for content embedded outside the app (e.g. email images). "
            "Capped server-side by MAX_SERVE_URL_EXPIRY. Omit for the "
            "default short-lived URL."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an asset with optional name and labels.
    
    This endpoint accepts multipart form data with the following fields:
    - file: The asset to upload (required)
    - name: Optional custom name for the asset
    - labels: Optional JSON string containing a dictionary of labels
    - extract_data: Optional boolean flag to extract data from the document using DocumentAnalyzer
    - expires_in: Optional seconds; requests a long-lived signed serve_url (e.g. for
      images embedded in outbound emails) instead of the default short-lived URL,
      capped by MAX_SERVE_URL_EXPIRY

    File size limits:
    - Default maximum: 100MB
    - Configurable via MAX_FILE_SIZE_MB environment variable
    
    Example using curl:
    ```bash
    curl -X POST "http://localhost:8000/assets" \
      -H "Authorization: Bearer YOUR_TOKEN" \
      -F "file=@/path/to/file.pdf" \
      -F "name=Custom Name" \
      -F "labels={\"emi\": 1234, \"hello\": \"asdf\"}" \
      -F "extract_data=true"
    ```
    
    Example using Python requests:
    ```python
    import requests
    
    files = {'file': open('file.pdf', 'rb')}
    data = {
        'name': 'Custom Name',
        'labels': json.dumps({'emi': 1234, 'hello': 'asdf'}),
        'extract_data': True
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

    storage = StorageFactory.get_backend()

    ctx = ProcessorContext(
        user_id=UUID(str(current_user.id)),
        project_id=project_id or "*",
    )
    config = (
        resolve_analysis_config(config_id, db) if (extract_data or summarize) else None
    )

    processors = []
    if extract_data:
        if config and config.provider == AnalysisProvider.MODELA:
            processors.append(ModelaAnalysisProcessor())
        else:
            from app.services.analysis.factory import AnalysisFactory

            if config is not None:
                backend = AnalysisFactory.get_backend(
                    config.provider, config.provider_params
                )
            else:
                backend = AnalysisFactory.get_backend()
            if backend:
                processors.append(AnalysisProcessor(backend))
    if summarize:
        if config and config.summarization_provider == AnalysisProvider.MODELA:
            processors.append(ModelaSummarizationProcessor())
        else:
            processors.append(SummarizationProcessor(ClaudeSummarizationService()))

    return await upload_asset(
        file=file,
        user_id=UUID(str(current_user.id)),
        db=db,
        storage=storage,
        name=name,
        labels=parsed_labels,
        processors=processors,
        ctx=ctx,
        expires_in=expires_in,
    )


class AssetDownloadRequest(BaseModel):
    """Request model for downloading assets from URLs."""

    url: str = Field(..., description="URL of the file to download")
    name: Optional[str] = Field(None, description="Optional custom name for the asset")
    labels: Optional[Dict[str, Any]] = Field(
        None, description="Optional labels for the asset"
    )


@router.post("/from-url", response_model=AssetUploadResponse)
async def create_asset_from_url(
    request: AssetDownloadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download a file from a URL and create an asset.

    This endpoint downloads a file from the provided URL and creates an asset record.
    The file is downloaded to a temporary location, then processed and stored like
    a regular file upload.

    Args:
        request: AssetDownloadRequest containing the URL and optional metadata

    Returns:
        AssetUploadResponse: Asset information including ID and URL

    Example request:
    ```json
    {
        "url": "https://www.hello.com/some-file.png",
        "name": "My Downloaded File",
        "labels": {
            "source": "external",
            "category": "image"
        }
    }
    ```
    """
    # Validate URL
    try:
        parsed_url = urlparse(request.url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL format")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {str(e)}")

    # Download the file
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(request.url, follow_redirects=True)
            response.raise_for_status()

            # Get content type and filename from response
            content_type = response.headers.get(
                "content-type", "application/octet-stream"
            )

            # Try to get filename from Content-Disposition header or URL
            filename = None
            content_disposition = response.headers.get("content-disposition", "")
            if "filename=" in content_disposition:
                filename = content_disposition.split("filename=")[1].strip('"')

            if not filename:
                # Extract filename from URL
                filename = os.path.basename(parsed_url.path)
                if not filename or "." not in filename:
                    # Generate filename based on content type
                    extension = (
                        content_type.split("/")[-1] if "/" in content_type else "bin"
                    )
                    filename = f"downloaded_file.{extension}"

            # Create a temporary file to store the downloaded content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name

            # Create a file wrapper to make downloaded content compatible with upload_asset
            class DownloadedFileWrapper:
                def __init__(
                    self, file_path: str, filename: str, content_type: str, size: int
                ):
                    self.file_path = file_path
                    self.filename = filename
                    self.content_type = content_type
                    self.size = size
                    self._file = None
                    # Create a file-like object that upload_asset expects
                    self.file = open(file_path, "rb")

                async def read(self, size: int = -1):
                    if not self._file:
                        self._file = open(self.file_path, "rb")
                    return self._file.read(size)

                def seek(self, offset: int, whence: int = 0):
                    if not self._file:
                        self._file = open(self.file_path, "rb")
                    return self._file.seek(offset, whence)

                def tell(self):
                    if not self._file:
                        self._file = open(self.file_path, "rb")
                    return self._file.tell()

                def close(self):
                    if self._file:
                        self._file.close()
                        self._file = None
                    if hasattr(self, "file") and self.file:
                        self.file.close()

                def __del__(self):
                    # Clean up temporary file
                    try:
                        if hasattr(self, "file") and self.file:
                            self.file.close()
                        os.unlink(self.file_path)
                    except:
                        pass

            # Create file wrapper for downloaded content
            downloaded_file = DownloadedFileWrapper(
                file_path=temp_file_path,
                filename=filename,
                content_type=content_type,
                size=len(response.content),
            )

            # Use the existing upload logic
            storage = StorageFactory.get_backend()

            return await upload_asset(
                file=downloaded_file,
                user_id=UUID(str(current_user.id)),
                db=db,
                storage=storage,
                name=request.name,
                labels=request.labels,
            )

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download file from URL: HTTP {e.response.status_code}",
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to download file from URL: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing downloaded file: {str(e)}"
        )


@router.delete("/{asset_id}", response_model=MessageResponse)
async def delete_asset(
    asset: Asset = Depends(get_asset_by_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cache: AssetCache = Depends(get_asset_cache),
):
    """
    Delete an asset by ID.

    The asset must exist and belong to the current user.
    Returns a success message with consistent response format.
    """
    if asset.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this asset"
        )

    success = DeleteAssetCommand(db, cache=cache).execute(asset.id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete asset")

    return MessageResponse(
        message="Asset deleted successfully", details={"asset_id": str(asset.id)}
    )
