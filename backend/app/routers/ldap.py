from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, models, schemas
from ..database import get_db
from ..radius_config import render_ldap_module

router = APIRouter(prefix="/api/ldap", tags=["ldap"])


def _serialize(row: models.LdapSettings) -> schemas.LdapSettingsOut:
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
        has_password=bool(row.bind_password),
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
