import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import auth as auth_mod
from . import ldap_sync
from .config import get_settings
from .database import SessionLocal, init_models
from .routers import (
    auth,
    clients,
    config,
    decisions,
    ldap,
    pools,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    async with SessionLocal() as db:
        await auth_mod.ensure_seed(db)
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
app.include_router(ldap.router, dependencies=_guard)
app.include_router(decisions.router, dependencies=_guard)
app.include_router(config.router, dependencies=_guard)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
