"""Database operations. Kept thin and explicit rather than a generic base
class, so each entity's quirks (pool ordering, realm pool names) stay readable.
"""
from sqlalchemy import delete, func, select
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


# --------------------------- Target servers -------------------------------
async def list_target_servers(db: AsyncSession) -> list[models.TargetServer]:
    res = await db.execute(
        select(models.TargetServer).order_by(models.TargetServer.name)
    )
    return list(res.scalars().all())


async def get_target_server(db: AsyncSession, ts_id: int) -> models.TargetServer | None:
    return await db.get(models.TargetServer, ts_id)


async def create_target_server(
    db: AsyncSession, data: schemas.TargetServerCreate
) -> models.TargetServer:
    ts = models.TargetServer(**data.model_dump())
    db.add(ts)
    await db.flush()
    await log(db, "create", "target_server", ts.name)
    await db.commit()
    await db.refresh(ts)
    return ts


async def update_target_server(
    db: AsyncSession, ts: models.TargetServer, data: schemas.TargetServerUpdate
) -> models.TargetServer:
    for k, v in data.model_dump().items():
        setattr(ts, k, v)
    await log(db, "update", "target_server", ts.name)
    await db.commit()
    await db.refresh(ts)
    return ts


async def delete_target_server(db: AsyncSession, ts: models.TargetServer) -> None:
    await log(db, "delete", "target_server", ts.name)
    await db.delete(ts)
    await db.commit()


# --------------------------- Clients (NAS) --------------------------------
async def list_clients(db: AsyncSession) -> list[models.Client]:
    res = await db.execute(select(models.Client).order_by(models.Client.name))
    return list(res.scalars().all())


async def get_client(db: AsyncSession, client_id: int) -> models.Client | None:
    return await db.get(models.Client, client_id)


async def create_client(
    db: AsyncSession, data: schemas.ClientCreate
) -> models.Client:
    client = models.Client(**data.model_dump())
    db.add(client)
    await db.flush()
    await log(db, "create", "client", client.name)
    await db.commit()
    await db.refresh(client)
    return client


async def update_client(
    db: AsyncSession, client: models.Client, data: schemas.ClientUpdate
) -> models.Client:
    for k, v in data.model_dump().items():
        setattr(client, k, v)
    await log(db, "update", "client", client.name)
    await db.commit()
    await db.refresh(client)
    return client


async def delete_client(db: AsyncSession, client: models.Client) -> None:
    await log(db, "delete", "client", client.name)
    await db.delete(client)
    await db.commit()


# --------------------------- Rules (routing) ------------------------------
def _rule_opts():
    return (
        selectinload(models.Rule.client),
        selectinload(models.Rule.target_pool),
    )


async def list_rules(db: AsyncSession) -> list[models.Rule]:
    res = await db.execute(
        select(models.Rule).options(*_rule_opts()).order_by(models.Rule.position)
    )
    return list(res.scalars().all())


async def get_rule(db: AsyncSession, rule_id: int) -> models.Rule | None:
    res = await db.execute(
        select(models.Rule).where(models.Rule.id == rule_id).options(*_rule_opts())
    )
    return res.scalar_one_or_none()


async def create_rule(db: AsyncSession, data: schemas.RuleCreate) -> models.Rule:
    maxpos = (
        await db.execute(select(func.coalesce(func.max(models.Rule.position), 0)))
    ).scalar_one()
    rule = models.Rule(position=int(maxpos) + 1, **data.model_dump())
    db.add(rule)
    await db.flush()
    await log(db, "create", "rule", rule.name or f"#{rule.id}")
    await db.commit()
    return await get_rule(db, rule.id)  # type: ignore[return-value]


async def update_rule(
    db: AsyncSession, rule: models.Rule, data: schemas.RuleUpdate
) -> models.Rule:
    for k, v in data.model_dump().items():
        setattr(rule, k, v)
    await log(db, "update", "rule", rule.name or f"#{rule.id}")
    await db.commit()
    return await get_rule(db, rule.id)  # type: ignore[return-value]


async def delete_rule(db: AsyncSession, rule: models.Rule) -> None:
    await log(db, "delete", "rule", rule.name or f"#{rule.id}")
    await db.delete(rule)
    await db.commit()


async def reorder_rules(db: AsyncSession, ids: list[int]) -> None:
    for pos, rid in enumerate(ids, start=1):
        r = await db.get(models.Rule, rid)
        if r is not None:
            r.position = pos
    await log(db, "reorder", "rules", f"{len(ids)} rules")
    await db.commit()


async def search_groups(
    db: AsyncSession, q: str = "", limit: int = 20
) -> list[models.AdGroupCatalog]:
    stmt = select(models.AdGroupCatalog).order_by(models.AdGroupCatalog.cn)
    if q:
        stmt = stmt.where(models.AdGroupCatalog.cn.ilike(f"%{q}%"))
    res = await db.execute(stmt.limit(min(limit, 50)))
    return list(res.scalars().all())


# --------------------------- Pools ----------------------------------------
async def list_pools(db: AsyncSession) -> list[models.HomeServerPool]:
    res = await db.execute(
        select(models.HomeServerPool)
        .options(
            selectinload(models.HomeServerPool.members).selectinload(
                models.PoolMember.target_server
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
                models.PoolMember.target_server
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
    for position, ts_id in enumerate(member_ids):
        db.add(
            models.PoolMember(
                pool_id=pool.id, target_server_id=ts_id, position=position
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


# --------------------------- LDAP / AD settings ---------------------------
async def get_ldap_settings(db: AsyncSession) -> models.LdapSettings:
    """Return the singleton row, creating it (id=1) on first access."""
    row = await db.get(models.LdapSettings, 1)
    if row is None:
        row = models.LdapSettings(id=1)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def update_ldap_settings(
    db: AsyncSession, data: schemas.LdapSettingsUpdate
) -> models.LdapSettings:
    row = await get_ldap_settings(db)
    payload = data.model_dump()
    password = payload.pop("bind_password", "")
    ca_cert = payload.pop("ca_cert", "")
    for k, v in payload.items():
        setattr(row, k, v)
    # Empty password/CA field = keep stored; "-" clears the CA.
    if password:
        row.bind_password = password
    if ca_cert == "-":
        row.ca_cert = ""
    elif ca_cert:
        row.ca_cert = ca_cert
    await log(db, "update", "ldap_settings", "ad")  # never log the secret
    await db.commit()
    await db.refresh(row)
    return row


async def recent_decisions(
    db: AsyncSession, limit: int = 100, username: str = "", realm: str = ""
) -> list[models.ProxyDecision]:
    q = select(models.ProxyDecision).order_by(models.ProxyDecision.id.desc())
    if username:
        q = q.where(models.ProxyDecision.username.ilike(f"%{username}%"))
    if realm:
        q = q.where(models.ProxyDecision.realm == realm)
    res = await db.execute(q.limit(min(limit, 500)))
    return list(res.scalars().all())


async def recent_audit(db: AsyncSession, limit: int = 50) -> list[models.AuditLog]:
    res = await db.execute(
        select(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(limit)
    )
    return list(res.scalars().all())
