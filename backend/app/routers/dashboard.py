import asyncio
import subprocess

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def _count(db: AsyncSession, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


def _fr_running() -> bool:
    try:
        return (
            subprocess.run(
                ["pgrep", "-x", "freeradius"], stdout=subprocess.DEVNULL
            ).returncode
            == 0
        )
    except Exception:  # noqa: BLE001
        return False


@router.get("")
async def dashboard(db: AsyncSession = Depends(get_db)):
    counts = {
        "clients": await _count(db, models.Client),
        "targets": await _count(db, models.TargetServer),
        "pools": await _count(db, models.HomeServerPool),
        "rules": await _count(db, models.Rule),
    }

    ldap = await db.get(models.LdapSettings, 1)
    auth = await db.get(models.AuthSettings, 1)
    tls = await db.get(models.TlsSettings, 1)

    sync_rows = (
        await db.execute(select(models.AdGroupSync))
    ).scalars().all()
    ad = {
        "enabled": bool(ldap and ldap.enabled),
        "catalog": await _count(db, models.AdGroupCatalog),
        "members": await _count(db, models.AdGroupMember),
        "groups_ok": sum(1 for r in sync_rows if r.status == "ok"),
        "groups_error": sum(1 for r in sync_rows if r.status == "error"),
        "last_sync": max(
            (r.last_synced_at.isoformat() for r in sync_rows if r.last_synced_at),
            default=None,
        ),
    }

    last_apply = (
        await db.execute(
            select(models.AuditLog)
            .where(models.AuditLog.action == "apply")
            .order_by(models.AuditLog.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    decisions = (
        await db.execute(
            select(models.ProxyDecision)
            .order_by(models.ProxyDecision.id.desc())
            .limit(5)
        )
    ).scalars().all()

    return {
        "counts": counts,
        "ad": ad,
        "freeradius_running": await asyncio.to_thread(_fr_running),
        "last_apply": (
            {
                "detail": last_apply.detail,
                "at": last_apply.created_at.isoformat() if last_apply.created_at else None,
            }
            if last_apply
            else None
        ),
        "security": {
            "auth_enabled": bool(auth and auth.enabled),
            "ip_restricted": bool(auth and (auth.ip_allowlist or "").strip()),
            "tls_self_signed": bool(tls.is_self_signed) if tls else True,
        },
        "recent_decisions": [
            {
                "at": d.created_at.isoformat() if d.created_at else None,
                "username": d.username,
                "realm": d.realm,
                "ad_result": d.ad_result,
                "reply": d.reply,
            }
            for d in decisions
        ],
    }
