from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.client_service import ClientService
from app.schemas.client import Client, ClientCreate, ClientUpdate
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=List[Client])
async def get_clients(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a list of clients with pagination."""
    client_service = ClientService(db)
    clients = client_service.get_clients(skip=skip, limit=limit)
    return clients


@router.get("/{client_id}", response_model=Client)
async def get_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific client by UUID."""
    client_service = ClientService(db)
    client = client_service.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("/by-client-id/{client_id}", response_model=Client)
async def get_client_by_client_id(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific client by client_id (slug)."""
    client_service = ClientService(db)
    client = client_service.get_client_by_client_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("", response_model=Client)
async def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new client."""
    client_service = ClientService(db)

    # Check if client_id already exists
    existing_client = client_service.get_client_by_client_id(client.client_id)
    if existing_client:
        raise HTTPException(status_code=400, detail="Client ID already exists")

    return client_service.create_client(client)


@router.put("/{client_id}", response_model=Client)
async def update_client(
    client_id: UUID,
    client: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing client."""
    client_service = ClientService(db)

    # Check if client exists
    existing_client = client_service.get_client(client_id)
    if not existing_client:
        raise HTTPException(status_code=404, detail="Client not found")

    # If client_id is being updated, check for uniqueness
    if client.client_id and client.client_id != existing_client.client_id:
        duplicate_client = client_service.get_client_by_client_id(client.client_id)
        if duplicate_client:
            raise HTTPException(status_code=400, detail="Client ID already exists")

    updated_client = client_service.update_client(client_id, client)
    return updated_client


@router.delete("/{client_id}")
async def delete_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a client."""
    client_service = ClientService(db)
    success = client_service.delete_client(client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted successfully"}


@router.post("/{client_id}/update-secret")
async def update_client_secret_timestamp(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the secret_generated_at timestamp for a client."""
    client_service = ClientService(db)
    client = client_service.update_secret_generated_at(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Secret timestamp updated successfully"}
