"""Async SQLAlchemy engine, session factory and Base."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

# check_same_thread is only meaningful for SQLite; ignored elsewhere.
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args=connect_args,
)

SessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


# proxy_decision columns FreeRADIUS's rlm_sql INSERT may omit; give them a DB
# default so an existing (pre-server_default) table doesn't reject the row with
# a NOT NULL violation. create_all can't alter existing columns and there is no
# Alembic — so nudge them here, idempotently, best-effort.
_PROXY_DECISION_DEFAULTS = (
    "nas_ip", "packet_src_ip", "username", "realm", "ad_result", "reply", "home_server",
)


async def _migrate() -> None:
    """Idempotent schema nudges create_all can't do on an existing table.
    Postgres only; a failure never blocks startup."""
    if not settings.database_url.startswith("postgresql"):
        return
    from sqlalchemy import text

    for col in _PROXY_DECISION_DEFAULTS:
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(f"ALTER TABLE proxy_decision ALTER COLUMN {col} SET DEFAULT ''")
                )
        except Exception:  # noqa: BLE001 — never block startup on a migration
            pass


async def init_models() -> None:
    """Create tables on startup. For real deployments use Alembic migrations."""
    from . import models  # noqa: F401 — ensure models are imported

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _migrate()
