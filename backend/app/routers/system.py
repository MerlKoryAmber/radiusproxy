import ipaddress
import os
import socket

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas, tls
from ..config import get_settings
from ..database import get_db

router = APIRouter(prefix="/api/system", tags=["system"])
settings = get_settings()


def _caller_ip(request: Request) -> str:
    xff = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


# --- IP access allowlist ---------------------------------------------------
@router.get("/access", response_model=schemas.AccessSettingsOut)
async def get_access(db: AsyncSession = Depends(get_db)):
    row = await crud.get_auth_settings(db)
    return schemas.AccessSettingsOut(ip_allowlist=row.ip_allowlist)


@router.put("/access", response_model=schemas.AccessSettingsOut)
async def set_access(
    data: schemas.AccessSettingsIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    entries = [
        e.strip()
        for e in (data.ip_allowlist or "").replace(",", "\n").splitlines()
        if e.strip()
    ]
    # Validate every entry parses; reject garbage so a typo can't lock everyone out.
    nets = []
    for e in entries:
        try:
            nets.append(ipaddress.ip_network(e, strict=False))
        except ValueError:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"invalid IP/CIDR: {e!r}",
            )
    # Anti-lockout: a non-empty list must still admit the caller's own IP.
    if nets:
        ip = _caller_ip(request)
        try:
            addr = ipaddress.ip_address(ip)
            covered = addr.is_loopback or any(addr in n for n in nets)
        except ValueError:
            covered = False
        if not covered:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"this allowlist would lock you out — add your own IP ({ip or 'unknown'})",
            )
    row = await crud.get_auth_settings(db)
    row.ip_allowlist = data.ip_allowlist
    await crud.log(db, "update", "access", "ip_allowlist")
    await db.commit()
    return schemas.AccessSettingsOut(ip_allowlist=row.ip_allowlist)


# --- RADIUS server tunables ------------------------------------------------
@router.get("/radius", response_model=schemas.RadiusSettingsOut)
async def get_radius(db: AsyncSession = Depends(get_db)):
    return await crud.get_radius_settings(db)


@router.put("/radius", response_model=schemas.RadiusSettingsOut)
async def set_radius(
    data: schemas.RadiusSettingsIn, db: AsyncSession = Depends(get_db)
):
    row = await crud.get_radius_settings(db)
    row.max_request_time = data.max_request_time
    await crud.log(db, "update", "radius", f"max_request_time={data.max_request_time}")
    await db.commit()
    # Re-apply so radiusd.conf is patched + FreeRADIUS reloaded.
    from ..radius_config import ConfigValidationError, apply_config

    try:
        await apply_config(db)
    except ConfigValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.output[-800:])
    await db.refresh(row)
    return row


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
    # HOST_HOSTNAME is the real host name (install.sh → .env); socket.gethostname()
    # would return the *container* id, which is meaningless in Settings → Host.
    hostname = os.environ.get("HOST_HOSTNAME", "").strip() or socket.gethostname()
    return schemas.HostInfoOut(hostname=hostname, addresses=tls.host_addresses())
