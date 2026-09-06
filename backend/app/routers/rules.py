from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _serialize(rule: models.Rule) -> schemas.RuleOut:
    out = schemas.RuleOut.model_validate(rule)
    out.client_name = rule.client.name if rule.client else None
    out.target_pool_name = rule.target_pool.name if rule.target_pool else None
    return out


@router.get("", response_model=list[schemas.RuleOut])
async def list_rules(db: AsyncSession = Depends(get_db)):
    return [_serialize(r) for r in await crud.list_rules(db)]


@router.post("", response_model=schemas.RuleOut, status_code=201)
async def create_rule(data: schemas.RuleCreate, db: AsyncSession = Depends(get_db)):
    return _serialize(await crud.create_rule(db, data))


@router.post("/reorder", status_code=204)
async def reorder_rules(data: schemas.RuleReorder, db: AsyncSession = Depends(get_db)):
    await crud.reorder_rules(db, data.ids)


@router.put("/{rule_id}", response_model=schemas.RuleOut)
async def update_rule(
    rule_id: int, data: schemas.RuleUpdate, db: AsyncSession = Depends(get_db)
):
    rule = await crud.get_rule(db, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rule not found")
    return _serialize(await crud.update_rule(db, rule, data))


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    rule = await crud.get_rule(db, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rule not found")
    await crud.delete_rule(db, rule)
