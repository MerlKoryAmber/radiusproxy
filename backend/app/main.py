import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import ipaddress

from . import auth as auth_mod
from . import ldap_sync, tls
from .config import get_settings
from .database import SessionLocal, init_models
from .routers import (
    auth,
    clients,
    config,
    dashboard,
    decisions,
    ldap,
    pools,
    rules,
    system,
    targets,
)
from fastapi import Depends

settings = get_settings()


async def _group_sync_loop():
    """Periodically pull AD group membership into the panel DB (ADR-0002).

    Interval is read from LdapSettings each cycle. Errors never kill the loop —
    a failed sync just leaves the last-known members in place.
    """
    from . import models

    while True:
        interval = 1800
        try:
            async with SessionLocal() as db:
                cfg = await db.get(models.LdapSettings, 1)
                interval = (cfg.group_sync_interval if cfg else 1800) or 1800
                if cfg and cfg.enabled:
                    await ldap_sync.sync_all(db)
        except Exception:  # noqa: BLE001 — loop must survive any failure
            pass
        await asyncio.sleep(max(60, interval))


async def _ensure_tls(db):
    """Load the panel cert from the DB (generate self-signed on first run) and
    materialise it to the shared volume the frontend nginx serves."""
    from . import crud, models

    row = await crud.get_tls_settings(db)
    if not row.cert_pem or not row.key_pem:
        cert_pem, key_pem = tls.generate_self_signed()
        row.cert_pem = cert_pem
        row.key_pem = key_pem
        row.is_self_signed = True
        await db.commit()
    try:
        tls.write_files(settings.tls_cert_dir, row.cert_pem, row.key_pem)
    except Exception:  # noqa: BLE001 — never block startup on cert write
        pass


@asynccontextmanager
async def _apply_on_boot(db):
    """Render the current DB config into FreeRADIUS and reload. The raddb lives
    in the image (not a volume), so a rebuilt/restarted backend starts with a
    stub site+policy; this makes the panel self-healing — real clients/rules
    are live without a manual apply. Best-effort: never block startup."""
    from .radius_config import apply_config

    try:
        await apply_config(db)
    except Exception:  # noqa: BLE001
        pass


async def lifespan(app: FastAPI):
    await init_models()
    async with SessionLocal() as db:
        await auth_mod.ensure_seed(db)
        await _ensure_tls(db)
        await _apply_on_boot(db)
    task = asyncio.create_task(_group_sync_loop())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title="FreeRADIUS Proxy Panel",
    version="0.1.0",
    description="Manage FreeRADIUS 3.2 proxy.conf — home servers, pools, realms.",
    lifespan=lifespan,
)

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


@app.exception_handler(IntegrityError)
async def _integrity_error(request: Request, exc: IntegrityError):
    # e.g. duplicate name / unique constraint — a client error, not a 500.
    return JSONResponse(
        status_code=409,
        content={"detail": "conflict: duplicate or constraint violation"},
    )


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


@app.middleware("http")
async def _ip_allowlist(request: Request, call_next):
    """Restrict /api access to an allowlist of IPs/CIDRs (loopback always OK).
    Empty allowlist = open. Reads AuthSettings each request (cheap)."""
    path = request.url.path
    if path.startswith("/api") and path != "/api/health":
        from . import models

        try:
            async with SessionLocal() as db:
                row = await db.get(models.AuthSettings, 1)
            allow = (row.ip_allowlist if row else "") or ""
            entries = [e.strip() for e in allow.replace(",", "\n").splitlines() if e.strip()]
            if entries:
                ip = _client_ip(request)
                ok = False
                try:
                    addr = ipaddress.ip_address(ip)
                    ok = addr.is_loopback or any(
                        addr in ipaddress.ip_network(e, strict=False) for e in entries
                    )
                except ValueError:
                    ok = False
                if not ok:
                    return JSONResponse(
                        status_code=403, content={"detail": "access denied for your IP"}
                    )
        except Exception:  # noqa: BLE001 — never hard-fail the request on this
            pass
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)  # open (login/status)

# All data/config routers require a valid token when auth is enabled.
_guard = [Depends(auth_mod.require_user)]
app.include_router(clients.router, dependencies=_guard)
app.include_router(targets.router, dependencies=_guard)
app.include_router(pools.router, dependencies=_guard)
app.include_router(rules.router, dependencies=_guard)
app.include_router(ldap.router, dependencies=_guard)
app.include_router(decisions.router, dependencies=_guard)
app.include_router(dashboard.router, dependencies=_guard)
app.include_router(system.router, dependencies=_guard)
app.include_router(config.router, dependencies=_guard)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
