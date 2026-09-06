from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/pools", tags=["pools"])


def _serialize(pool: models.HomeServerPool) -> schemas.PoolOut:
    members = sorted(pool.members, key=lambda m: m.position)
    return schemas.PoolOut(
        id=pool.id,
        name=pool.name,
        type=pool.type,
        enabled=pool.enabled,
        note=pool.note,
        members=[
            schemas.PoolMemberOut(
                target_server_id=m.target_server_id,
                position=m.position,
                name=m.target_server.name,
            )
            for m in members
        ],
    )


@router.get("", response_model=list[schemas.PoolOut])
async def list_pools(db: AsyncSession = Depends(get_db)):
    return [_serialize(p) for p in await crud.list_pools(db)]


@router.post("", response_model=schemas.PoolOut, status_code=201)
async def create_pool(data: schemas.PoolCreate, db: AsyncSession = Depends(get_db)):
    return _serialize(await crud.create_pool(db, data))


@router.put("/{pool_id}", response_model=schemas.PoolOut)
async def update_pool(
    pool_id: int, data: schemas.PoolUpdate, db: AsyncSession = Depends(get_db)
):
    pool = await crud.get_pool(db, pool_id)
    if not pool:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pool not found")
    return _serialize(await crud.update_pool(db, pool, data))


@router.delete("/{pool_id}", status_code=204)
async def delete_pool(pool_id: int, db: AsyncSession = Depends(get_db)):
    pool = await crud.get_pool(db, pool_id)
    if not pool:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pool not found")
    await crud.delete_pool(db, pool)
