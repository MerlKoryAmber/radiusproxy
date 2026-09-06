from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud
from ..database import get_db

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


@router.get("")
async def list_decisions(
    limit: int = 100,
    username: str = "",
    realm: str = "",
    db: AsyncSession = Depends(get_db),
):
    rows = await crud.recent_decisions(db, limit=limit, username=username, realm=realm)
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "nas_ip": r.nas_ip,
            "packet_src_ip": r.packet_src_ip,
            "username": r.username,
            "realm": r.realm,
            "ad_result": r.ad_result,
            "reply": r.reply,
            "home_server": r.home_server,
        }
        for r in rows
    ]
