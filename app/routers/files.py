from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
from app.storage.base import StorageBackend
from app.storage.local import LocalStorageBackend
from app.storage.factory import StorageFactory
import os
from pathlib import Path

router = APIRouter(prefix="/files", tags=["files"])


def get_storage_backend() -> StorageBackend:
    """Get the configured storage backend."""
    return StorageFactory.get_backend()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    is_public: bool = False,
    storage: StorageBackend = Depends(get_storage_backend),
):
    """Upload a file."""
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Save the file
    saved_filename = await storage.save(filename, file, is_public)
    
    # Get the URL for accessing the file
    url = await storage.get_url(saved_filename, is_public)
    
    return {
        "filename": saved_filename,
        "url": url,
        "is_public": is_public,
    }


@router.get("/download/{token}")
async def download_file(
    token: str,
    storage: StorageBackend = Depends(get_storage_backend),
):
    """Download a private file using a signed token."""
    if not isinstance(storage, LocalStorageBackend):
        raise HTTPException(
            status_code=400,
            detail="Token-based downloads are only supported with local storage"
        )
    
    # Verify the token and get the filename
    filename = storage.verify_token(token)
    
    # Get the file path
    file_path = storage.private_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/octet-stream"
    ) 