from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/clients", tags=["clients"])


def _serialize(client: models.Client) -> schemas.ClientOut:
    out = schemas.ClientOut.model_validate(client)
    out.target_pool_name = client.target_pool.name if client.target_pool else None
    return out


@router.get("", response_model=list[schemas.ClientOut])
async def list_clients(db: AsyncSession = Depends(get_db)):
    return [_serialize(c) for c in await crud.list_clients(db)]


@router.post("", response_model=schemas.ClientOut, status_code=201)
async def create_client(data: schemas.ClientCreate, db: AsyncSession = Depends(get_db)):
    return _serialize(await crud.create_client(db, data))


@router.put("/{client_id}", response_model=schemas.ClientOut)
async def update_client(
    client_id: int, data: schemas.ClientUpdate, db: AsyncSession = Depends(get_db)
):
    client = await crud.get_client(db, client_id)
    if not client:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "client not found")
    return _serialize(await crud.update_client(db, client, data))


@router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db)):
    client = await crud.get_client(db, client_id)
    if not client:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "client not found")
    await crud.delete_client(db, client)
