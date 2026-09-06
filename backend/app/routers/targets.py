from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/target-servers", tags=["target-servers"])


def _serialize(ts: models.TargetServer) -> schemas.TargetServerOut:
    out = schemas.TargetServerOut.model_validate(ts)
    out.has_secret = bool(ts.secret)
    return out


@router.get("", response_model=list[schemas.TargetServerOut])
async def list_target_servers(db: AsyncSession = Depends(get_db)):
    return [_serialize(t) for t in await crud.list_target_servers(db)]


@router.post("", response_model=schemas.TargetServerOut, status_code=201)
async def create_target_server(
    data: schemas.TargetServerCreate, db: AsyncSession = Depends(get_db)
):
    return _serialize(await crud.create_target_server(db, data))


@router.put("/{ts_id}", response_model=schemas.TargetServerOut)
async def update_target_server(
    ts_id: int, data: schemas.TargetServerUpdate, db: AsyncSession = Depends(get_db)
):
    ts = await crud.get_target_server(db, ts_id)
    if not ts:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "target server not found")
    return _serialize(await crud.update_target_server(db, ts, data))


@router.delete("/{ts_id}", status_code=204)
async def delete_target_server(ts_id: int, db: AsyncSession = Depends(get_db)):
    ts = await crud.get_target_server(db, ts_id)
    if not ts:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "target server not found")
    await crud.delete_target_server(db, ts)
