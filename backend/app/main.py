from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_models
from .routers import config, home_servers, ldap, pools, realms

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    yield


app = FastAPI(
    title="FreeRADIUS Proxy Panel",
    version="0.1.0",
    description="Manage FreeRADIUS 3.2 proxy.conf — home servers, pools, realms.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(home_servers.router)
app.include_router(pools.router)
app.include_router(realms.router)
app.include_router(ldap.router)
app.include_router(config.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
