from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi_pagination.ext.sqlalchemy import paginate
from app.commands.clients.create_client_command import CreateClientCommand
from app.commands.clients.delete_client_command import DeleteClientCommand
from app.commands.clients.update_client_command import UpdateClientCommand
from app.db import get_db
from app.models.client import Client as ClientModel
from app.repositories.client_repository import ClientRepository
from app.schemas.client import Client, ClientCreate, ClientUpdate, ClientWithSecret
from app.schemas.common import MessageResponse
from app.models.user import User
from app.utils.auth import get_current_user
from app.routers.utils.dependencies import get_client_by_id, get_client_by_slug
from app.auth.rbac import build_rbac_dependencies
from fastapi_pagination import Page, Params
from fastapi import Request
from typing import Optional

router = APIRouter(prefix="/clients", tags=["clients"])


async def infer_domain(request: Request) -> Optional[str]:
    return "*"


RESOURCE_CREDENTIALS = "client"
rbac = build_rbac_dependencies(
    resource=RESOURCE_CREDENTIALS,
    domain_resolver=infer_domain,
)


@router.get("", response_model=Page[Client])
def get_clients(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
    params: Params = Depends(),
    _authorized: bool = Depends(rbac["read"]),
) -> Page[Client]:
    """Get a paginated list of clients."""
    return paginate(db, select(ClientModel), params=params)


@router.get("/{client_id}", response_model=Client)
def get_client(
    client: ClientModel = Depends(get_client_by_id),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get a specific client by UUID."""
    return client


@router.get("/by-client-id/{client_id}", response_model=Client)
def get_client_by_client_id(
    client: ClientModel = Depends(get_client_by_slug),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["read"]),
):
    """Get a specific client by client_id (slug)."""
    return client


@router.post("", response_model=ClientWithSecret)
def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["create"]),
):
    """Create a new client and return it with the derived secret."""
    try:
        return CreateClientCommand(db).execute(client)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{client_id}", response_model=Client)
def update_client(
    client_update: ClientUpdate,
    client: ClientModel = Depends(get_client_by_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["update"]),
):
    """Update an existing client."""
    try:
        return UpdateClientCommand(db).execute(client, client_update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{client_id}", response_model=MessageResponse)
def delete_client(
    client: ClientModel = Depends(get_client_by_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["delete"]),
):
    """Delete a client."""
    DeleteClientCommand(db).execute(client)
    return MessageResponse(
        message="Client deleted successfully", details={"client_id": str(client.id)}
    )


@router.post("/{client_id}/regenerate-secret", response_model=ClientWithSecret)
def regenerate_client_secret(
    client: ClientModel = Depends(get_client_by_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _authorized: bool = Depends(rbac["update"]),
):
    """Regenerate the secret for a client and return the new secret."""
    regenerated = ClientRepository(db).regenerate_secret(client.id)
    if not regenerated:
        raise HTTPException(status_code=404, detail="Client not found")
    return regenerated
