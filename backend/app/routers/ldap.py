from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from .. import crud, ldap_sync, models, schemas, tls
from ..database import get_db
from ..radius_config import render_ldap_module

router = APIRouter(prefix="/api/ldap", tags=["ldap"])


def _serialize(row: models.LdapSettings) -> schemas.LdapSettingsOut:
    ca = (row.ca_cert or "").strip()
    ca_summ = tls.cert_summary(ca) if ca else {}
    return schemas.LdapSettingsOut(
        enabled=row.enabled,
        server=row.server,
        port=row.port,
        use_ldaps=row.use_ldaps,
        start_tls=row.start_tls,
        bind_dn=row.bind_dn,
        base_dn=row.base_dn,
        group_base_dn=row.group_base_dn,
        group_filter=row.group_filter,
        group_membership_attribute=row.group_membership_attribute,
        cache_ttl=row.cache_ttl,
        net_timeout=row.net_timeout,
        group_sync_interval=row.group_sync_interval,
        tls_require_cert=row.tls_require_cert,
        tls_min_version=row.tls_min_version,
        has_password=bool(row.bind_password),
        has_ca_cert=bool(ca),
        ca_subject=ca_summ.get("subject", ""),
        ca_not_after=ca_summ.get("not_after", ""),
    )


@router.get("", response_model=schemas.LdapSettingsOut)
async def get_ldap(db: AsyncSession = Depends(get_db)):
    return _serialize(await crud.get_ldap_settings(db))


@router.put("", response_model=schemas.LdapSettingsOut)
async def update_ldap(
    data: schemas.LdapSettingsUpdate, db: AsyncSession = Depends(get_db)
):
    return _serialize(await crud.update_ldap_settings(db, data))


@router.get("/preview.conf", response_class=PlainTextResponse)
async def preview_module(db: AsyncSession = Depends(get_db)):
    # Password masked — the preview is served to the browser.
    row = await crud.get_ldap_settings(db)
    return render_ldap_module(row, mask_password=True)


@router.get("/ca.pem", response_class=PlainTextResponse)
async def download_ca(db: AsyncSession = Depends(get_db)):
    # CA cert is public; return the stored PEM (empty if none).
    row = await crud.get_ldap_settings(db)
    return row.ca_cert or ""


@router.get("/sync")
async def sync_status(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(models.AdGroupSync).order_by(models.AdGroupSync.group_dn)
        )
    ).scalars().all()
    return [
        {
            "group_dn": r.group_dn,
            "status": r.status,
            "member_count": r.member_count,
            "error": r.error,
            "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
        }
        for r in rows
    ]


@router.post("/test")
async def test_ldap(db: AsyncSession = Depends(get_db)):
    """Connectivity/bind check against the *saved* settings (the bind password
    is write-only, so save before testing). Never raises — returns a structured
    result the UI renders as pass/fail with a reason."""
    import asyncio

    cfg = await crud.get_ldap_settings(db)
    result = await asyncio.to_thread(ldap_sync.test_connection, cfg)
    await crud.log(db, "test", "ldap", "ok" if result.get("ok") else "failed")
    await db.commit()
    return result


@router.post("/sync")
async def sync_now(db: AsyncSession = Depends(get_db)):
    cfg = await db.get(models.LdapSettings, 1)
    if not cfg or not cfg.enabled:
        return {"synced": [], "enabled": False, "summary": "AD checking is disabled"}
    results = await ldap_sync.sync_all(db)
    await crud.log(db, "sync", "ad_groups", f"{len(results)} groups")
    await db.commit()
    # Compact summary for the UI (catalog size + per-group ok/error counts).
    catalog = next(
        (r.get("catalog") for r in results if isinstance(r.get("catalog"), int)), None
    )
    groups = [r for r in results if "group_dn" in r]
    ok = sum(1 for r in groups if r.get("status") == "ok")
    err = sum(1 for r in groups if r.get("status") == "error")
    return {
        "synced": results,
        "enabled": True,
        "catalog": catalog,
        "groups_ok": ok,
        "groups_error": err,
    }


@router.get("/groups", response_model=list[schemas.AdGroupOut])
async def search_groups(q: str = "", db: AsyncSession = Depends(get_db)):
    rows = await crud.search_groups(db, q=q)
    return [schemas.AdGroupOut(cn=r.cn, dn=r.dn) for r in rows]
