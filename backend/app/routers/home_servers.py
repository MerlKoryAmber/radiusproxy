from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/api/home-servers", tags=["home-servers"])


@router.get("", response_model=list[schemas.HomeServerOut])
async def list_home_servers(db: AsyncSession = Depends(get_db)):
    return await crud.list_home_servers(db)


@router.post("", response_model=schemas.HomeServerOut, status_code=201)
async def create_home_server(
    data: schemas.HomeServerCreate, db: AsyncSession = Depends(get_db)
):
    return await crud.create_home_server(db, data)


@router.put("/{hs_id}", response_model=schemas.HomeServerOut)
async def update_home_server(
    hs_id: int, data: schemas.HomeServerUpdate, db: AsyncSession = Depends(get_db)
):
    hs = await crud.get_home_server(db, hs_id)
    if not hs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "home server not found")
    return await crud.update_home_server(db, hs, data)


@router.delete("/{hs_id}", status_code=204)
async def delete_home_server(hs_id: int, db: AsyncSession = Depends(get_db)):
    hs = await crud.get_home_server(db, hs_id)
    if not hs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "home server not found")
    await crud.delete_home_server(db, hs)
