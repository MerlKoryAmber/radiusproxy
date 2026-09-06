from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/realms", tags=["realms"])


def _serialize(realm: models.Realm) -> schemas.RealmOut:
    return schemas.RealmOut(
        id=realm.id,
        name=realm.name,
        auth_pool_id=realm.auth_pool_id,
        acct_pool_id=realm.acct_pool_id,
        nostrip=realm.nostrip,
        enabled=realm.enabled,
        note=realm.note,
        auth_pool_name=realm.auth_pool.name if realm.auth_pool else None,
        acct_pool_name=realm.acct_pool.name if realm.acct_pool else None,
    )


@router.get("", response_model=list[schemas.RealmOut])
async def list_realms(db: AsyncSession = Depends(get_db)):
    return [_serialize(r) for r in await crud.list_realms(db)]


@router.post("", response_model=schemas.RealmOut, status_code=201)
async def create_realm(data: schemas.RealmCreate, db: AsyncSession = Depends(get_db)):
    return _serialize(await crud.create_realm(db, data))


@router.put("/{realm_id}", response_model=schemas.RealmOut)
async def update_realm(
    realm_id: int, data: schemas.RealmUpdate, db: AsyncSession = Depends(get_db)
):
    realm = await crud.get_realm(db, realm_id)
    if not realm:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "realm not found")
    return _serialize(await crud.update_realm(db, realm, data))


@router.delete("/{realm_id}", status_code=204)
async def delete_realm(realm_id: int, db: AsyncSession = Depends(get_db)):
    realm = await crud.get_realm(db, realm_id)
    if not realm:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "realm not found")
    await crud.delete_realm(db, realm)
