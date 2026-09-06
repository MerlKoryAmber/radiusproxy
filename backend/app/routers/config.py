from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas
from ..database import get_db
from ..radius_config import (
    ConfigValidationError,
    apply_config,
    render_clients_conf,
    render_policy_conf,
    render_proxy_conf,
)

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/preview", response_model=schemas.ConfigPreview)
async def preview(db: AsyncSession = Depends(get_db)):
    return schemas.ConfigPreview(content=await render_proxy_conf(db))


@router.get("/preview.conf", response_class=PlainTextResponse)
async def preview_raw(db: AsyncSession = Depends(get_db)):
    return await render_proxy_conf(db)


@router.get("/clients-preview.conf", response_class=PlainTextResponse)
async def preview_clients(db: AsyncSession = Depends(get_db)):
    return await render_clients_conf(db)


@router.get("/policy-preview.conf", response_class=PlainTextResponse)
async def preview_policy(db: AsyncSession = Depends(get_db)):
    return await render_policy_conf(db)


@router.post("/apply", response_model=schemas.ApplyResponse)
async def apply(db: AsyncSession = Depends(get_db)):
    try:
        result = await apply_config(db)
    except ConfigValidationError as exc:
        # Config was rejected by radiusd -XC. The live files are untouched.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "FreeRADIUS rejected the config", "output": exc.output},
        )
    await crud.log(
        db, "apply", "config", f"{len(result.written_paths)} files",
        detail=(
            f"validated={result.validated} reloaded={result.reloaded} | "
            + ", ".join(result.written_paths)
        ),
    )
    await db.commit()
    return schemas.ApplyResponse(**result.__dict__)


@router.get("/audit")
async def audit(db: AsyncSession = Depends(get_db)):
    rows = await crud.recent_audit(db)
    return [
        {
            "id": r.id,
            "actor": r.actor,
            "action": r.action,
            "entity": r.entity,
            "entity_ref": r.entity_ref,
            "detail": r.detail,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
