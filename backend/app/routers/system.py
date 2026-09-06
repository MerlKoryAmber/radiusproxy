import socket

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas, tls
from ..config import get_settings
from ..database import get_db

router = APIRouter(prefix="/api/system", tags=["system"])
settings = get_settings()


# --- IP access allowlist ---------------------------------------------------
@router.get("/access", response_model=schemas.AccessSettingsOut)
async def get_access(db: AsyncSession = Depends(get_db)):
    row = await crud.get_auth_settings(db)
    return schemas.AccessSettingsOut(ip_allowlist=row.ip_allowlist)


@router.put("/access", response_model=schemas.AccessSettingsOut)
async def set_access(data: schemas.AccessSettingsIn, db: AsyncSession = Depends(get_db)):
    row = await crud.get_auth_settings(db)
    row.ip_allowlist = data.ip_allowlist
    await crud.log(db, "update", "access", "ip_allowlist")
    await db.commit()
    return schemas.AccessSettingsOut(ip_allowlist=row.ip_allowlist)


# --- TLS certificate -------------------------------------------------------
@router.get("/tls", response_model=schemas.TlsOut)
async def get_tls(db: AsyncSession = Depends(get_db)):
    row = await crud.get_tls_settings(db)
    summ = tls.cert_summary(row.cert_pem) if row.cert_pem else {}
    return schemas.TlsOut(
        has_cert=bool(row.cert_pem),
        is_self_signed=row.is_self_signed,
        subject=summ.get("subject", ""),
        issuer=summ.get("issuer", ""),
        not_after=summ.get("not_after", ""),
    )


@router.put("/tls", response_model=schemas.TlsOut)
async def replace_tls(data: schemas.TlsReplaceIn, db: AsyncSession = Depends(get_db)):
    try:
        summ = tls.validate(data.cert_pem, data.key_pem)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    row = await crud.get_tls_settings(db)
    row.cert_pem = data.cert_pem
    row.key_pem = data.key_pem
    row.is_self_signed = False
    await crud.log(db, "update", "tls", "cert replaced")
    await db.commit()
    # Materialise so nginx (watching the volume) picks it up.
    try:
        tls.write_files(settings.tls_cert_dir, data.cert_pem, data.key_pem)
    except Exception:  # noqa: BLE001
        pass
    return schemas.TlsOut(
        has_cert=True, is_self_signed=False,
        subject=summ.get("subject", ""), not_after=summ.get("not_after", ""),
    )


@router.post("/tls/self-signed", response_model=schemas.TlsOut)
async def regen_self_signed(db: AsyncSession = Depends(get_db)):
    cert_pem, key_pem = tls.generate_self_signed()
    row = await crud.get_tls_settings(db)
    row.cert_pem, row.key_pem, row.is_self_signed = cert_pem, key_pem, True
    await crud.log(db, "update", "tls", "self-signed regenerated")
    await db.commit()
    try:
        tls.write_files(settings.tls_cert_dir, cert_pem, key_pem)
    except Exception:  # noqa: BLE001
        pass
    summ = tls.cert_summary(cert_pem)
    return schemas.TlsOut(has_cert=True, is_self_signed=True, **{
        k: summ.get(k, "") for k in ("subject", "issuer", "not_after")
    })


# --- Host info (read-only) -------------------------------------------------
@router.get("/host", response_model=schemas.HostInfoOut)
async def host_info():
    return schemas.HostInfoOut(hostname=socket.gethostname(), addresses=tls.host_addresses())
