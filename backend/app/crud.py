"""Database operations. Kept thin and explicit rather than a generic base
class, so each entity's quirks (pool ordering, realm pool names) stay readable.
"""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import models, schemas


async def log(
    db: AsyncSession,
    action: str,
    entity: str,
    entity_ref: str = "",
    detail: str = "",
    actor: str = "admin",
) -> None:
    db.add(
        models.AuditLog(
            action=action,
            entity=entity,
            entity_ref=entity_ref,
            detail=detail,
            actor=actor,
        )
    )


# --------------------------- Home servers ---------------------------------
async def list_home_servers(db: AsyncSession) -> list[models.HomeServer]:
    res = await db.execute(select(models.HomeServer).order_by(models.HomeServer.name))
    return list(res.scalars().all())


async def get_home_server(db: AsyncSession, hs_id: int) -> models.HomeServer | None:
    return await db.get(models.HomeServer, hs_id)


async def create_home_server(
    db: AsyncSession, data: schemas.HomeServerCreate
) -> models.HomeServer:
    hs = models.HomeServer(**data.model_dump())
    db.add(hs)
    await db.flush()
    await log(db, "create", "home_server", hs.name)
    await db.commit()
    await db.refresh(hs)
    return hs


async def update_home_server(
    db: AsyncSession, hs: models.HomeServer, data: schemas.HomeServerUpdate
) -> models.HomeServer:
    for k, v in data.model_dump().items():
        setattr(hs, k, v)
    await log(db, "update", "home_server", hs.name)
    await db.commit()
    await db.refresh(hs)
    return hs


async def delete_home_server(db: AsyncSession, hs: models.HomeServer) -> None:
    await log(db, "delete", "home_server", hs.name)
    await db.delete(hs)
    await db.commit()


# --------------------------- Pools ----------------------------------------
async def list_pools(db: AsyncSession) -> list[models.HomeServerPool]:
    res = await db.execute(
        select(models.HomeServerPool)
        .options(
            selectinload(models.HomeServerPool.members).selectinload(
                models.PoolMember.home_server
            )
        )
        .order_by(models.HomeServerPool.name)
    )
    return list(res.scalars().all())


async def get_pool(db: AsyncSession, pool_id: int) -> models.HomeServerPool | None:
    res = await db.execute(
        select(models.HomeServerPool)
        .where(models.HomeServerPool.id == pool_id)
        .options(
            selectinload(models.HomeServerPool.members).selectinload(
                models.PoolMember.home_server
            )
        )
    )
    return res.scalar_one_or_none()


async def _set_members(
    db: AsyncSession, pool: models.HomeServerPool, member_ids: list[int]
) -> None:
    await db.execute(
        delete(models.PoolMember).where(models.PoolMember.pool_id == pool.id)
    )
    for position, hs_id in enumerate(member_ids):
        db.add(
            models.PoolMember(
                pool_id=pool.id, home_server_id=hs_id, position=position
            )
        )


async def create_pool(
    db: AsyncSession, data: schemas.PoolCreate
) -> models.HomeServerPool:
    payload = data.model_dump()
    member_ids = payload.pop("member_ids", [])
    pool = models.HomeServerPool(**payload)
    db.add(pool)
    await db.flush()
    await _set_members(db, pool, member_ids)
    await log(db, "create", "pool", pool.name)
    await db.commit()
    return await get_pool(db, pool.id)  # type: ignore[return-value]


async def update_pool(
    db: AsyncSession, pool: models.HomeServerPool, data: schemas.PoolUpdate
) -> models.HomeServerPool:
    payload = data.model_dump()
    member_ids = payload.pop("member_ids", [])
    for k, v in payload.items():
        setattr(pool, k, v)
    await db.flush()
    await _set_members(db, pool, member_ids)
    await log(db, "update", "pool", pool.name)
    await db.commit()
    return await get_pool(db, pool.id)  # type: ignore[return-value]


async def delete_pool(db: AsyncSession, pool: models.HomeServerPool) -> None:
    await log(db, "delete", "pool", pool.name)
    await db.delete(pool)
    await db.commit()


# --------------------------- Realms ---------------------------------------
async def list_realms(db: AsyncSession) -> list[models.Realm]:
    res = await db.execute(
        select(models.Realm)
        .options(
            selectinload(models.Realm.auth_pool),
            selectinload(models.Realm.acct_pool),
        )
        .order_by(models.Realm.name)
    )
    return list(res.scalars().all())


async def get_realm(db: AsyncSession, realm_id: int) -> models.Realm | None:
    res = await db.execute(
        select(models.Realm)
        .where(models.Realm.id == realm_id)
        .options(
            selectinload(models.Realm.auth_pool),
            selectinload(models.Realm.acct_pool),
        )
    )
    return res.scalar_one_or_none()


async def create_realm(db: AsyncSession, data: schemas.RealmCreate) -> models.Realm:
    realm = models.Realm(**data.model_dump())
    db.add(realm)
    await db.flush()
    await log(db, "create", "realm", realm.name)
    await db.commit()
    return await get_realm(db, realm.id)  # type: ignore[return-value]


async def update_realm(
    db: AsyncSession, realm: models.Realm, data: schemas.RealmUpdate
) -> models.Realm:
    for k, v in data.model_dump().items():
        setattr(realm, k, v)
    await log(db, "update", "realm", realm.name)
    await db.commit()
    return await get_realm(db, realm.id)  # type: ignore[return-value]


async def delete_realm(db: AsyncSession, realm: models.Realm) -> None:
    await log(db, "delete", "realm", realm.name)
    await db.delete(realm)
    await db.commit()


async def recent_audit(db: AsyncSession, limit: int = 50) -> list[models.AuditLog]:
    res = await db.execute(
        select(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(limit)
    )
    return list(res.scalars().all())
