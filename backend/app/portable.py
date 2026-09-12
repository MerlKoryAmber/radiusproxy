"""Portable config bundle (ADR-0007).

Export the panel's routing data (target servers / pools / clients / rules) to a
name-referenced JSON, and import such a bundle back with a dry-run plan before
writing. Entities reference each other by NAME (not DB id) so a file stays
readable and portable across databases. Main use: migrate a Windows NPS setup
into the panel (I fill the JSON from an NPS `netsh nps export` + screenshots).

Secrets are NOT exported (write-only at rest, ADR-0005); on import a secret is
required only when creating a new target/client, and empty = keep existing.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import crud, models, schemas

# Plain scalar fields copied verbatim (name/secret/refs handled separately).
_TARGET_FIELDS = (
    "type", "ipaddr", "port", "require_message_authenticator", "status_check",
    "response_window", "zombie_period", "revive_interval", "check_interval",
    "num_answers_to_alive", "enabled", "note",
)
_POOL_FIELDS = ("type", "enabled", "note")
_CLIENT_FIELDS = (
    "ipaddr", "shortname", "nas_type", "proto", "require_message_authenticator",
    "preserve_source_ip", "enabled", "note",
)


# --------------------------- export ---------------------------------------
async def export_bundle(db: AsyncSession) -> dict:
    targets = await crud.list_target_servers(db)
    pools = await crud.list_pools(db)
    clients = await crud.list_clients(db)
    rules = await crud.list_rules(db)
    return {
        "version": 1,
        "source": "radiusproxy",
        "target_servers": [
            {"name": t.name, **{f: getattr(t, f) for f in _TARGET_FIELDS}, "secret": ""}
            for t in targets
        ],
        "pools": [
            {
                "name": p.name,
                **{f: getattr(p, f) for f in _POOL_FIELDS},
                "members": [m.target_server.name for m in p.members],
            }
            for p in pools
        ],
        "clients": [
            {"name": c.name, **{f: getattr(c, f) for f in _CLIENT_FIELDS}, "secret": ""}
            for c in clients
        ],
        "rules": [
            {
                "name": r.name,
                "client": r.client.name if r.client else "",
                "target_pool": r.target_pool.name if r.target_pool else None,
                "match_username": r.match_username,
                "ad_group_check": r.ad_group_check,
                "required_ad_group": r.required_ad_group,
                "required_ad_group_dn": r.required_ad_group_dn,
                "username_normalization": r.username_normalization,
                "ad_fail_mode": r.ad_fail_mode,
                "pool_down_fallback": r.pool_down_fallback,
                "enabled": r.enabled,
                "note": r.note,
            }
            for r in rules
        ],
    }


# --------------------------- import ---------------------------------------
def _counts(items: list, problems: list) -> dict:
    return {
        "create": sum(1 for i in items if i.action == "create"),
        "update": sum(1 for i in items if i.action == "update"),
        "problems": len(problems),
    }


async def _resolve_dn(db: AsyncSession, cn: str) -> str:
    """Best-effort cn → DN from the synced AD catalog. Empty on miss/ambiguous
    (the panel's autocomplete resolves it later; the gate needs the DN)."""
    if not cn:
        return ""
    res = await db.execute(
        select(models.AdGroupCatalog).where(models.AdGroupCatalog.cn == cn)
    )
    rows = list(res.scalars().all())
    return rows[0].dn if len(rows) == 1 else ""


async def plan_and_apply(
    db: AsyncSession, bundle: schemas.ImportBundle, *, dry_run: bool
) -> schemas.ImportPlan:
    """Validate references, build a per-entity plan, and (unless dry_run) apply
    it in one transaction. Match by NAME: existing → update, else → create.
    Rules with an empty name always create (can't be matched)."""
    problems: list[schemas.ImportProblem] = []

    existing_targets = {t.name: t for t in await crud.list_target_servers(db)}
    existing_pools = {p.name: p for p in await crud.list_pools(db)}
    existing_clients = {c.name: c for c in await crud.list_clients(db)}
    existing_rules = {r.name: r for r in await crud.list_rules(db) if r.name}

    target_names = set(existing_targets) | {t.name for t in bundle.target_servers}
    pool_names = set(existing_pools) | {p.name for p in bundle.pools}
    client_names = set(existing_clients) | {c.name for c in bundle.clients}

    def P(kind: str, name: str, err: str) -> schemas.ImportProblem:
        return schemas.ImportProblem(kind=kind, name=name, error=err)

    # --- validate (no writes) ---
    for t in bundle.target_servers:
        if t.name not in existing_targets and not t.secret:
            problems.append(P("target_server", t.name, "secret required to create"))
    for p in bundle.pools:
        for m in p.members:
            if m not in target_names:
                problems.append(P("pool", p.name, f"unknown target server: {m}"))
    for c in bundle.clients:
        if c.name not in existing_clients and not c.secret:
            problems.append(P("client", c.name, "secret required to create"))
    for r in bundle.rules:
        label = r.name or f"{r.client}/{r.match_username or '*'}"
        if r.client not in client_names:
            problems.append(P("rule", label, f"unknown client: {r.client}"))
        if r.target_pool and r.target_pool not in pool_names:
            problems.append(P("rule", label, f"unknown pool: {r.target_pool}"))

    if problems:
        return schemas.ImportPlan(
            dry_run=dry_run, applied=False, items=[], problems=problems,
            counts=_counts([], problems),
        )

    # --- plan items ---
    items: list[schemas.ImportItem] = []
    for t in bundle.target_servers:
        items.append(schemas.ImportItem(
            kind="target_server", name=t.name,
            action="update" if t.name in existing_targets else "create",
        ))
    for p in bundle.pools:
        items.append(schemas.ImportItem(
            kind="pool", name=p.name,
            action="update" if p.name in existing_pools else "create",
            note=f"{len(p.members)} member(s)",
        ))
    for c in bundle.clients:
        items.append(schemas.ImportItem(
            kind="client", name=c.name,
            action="update" if c.name in existing_clients else "create",
            note="secret set" if c.secret else "keep secret",
        ))
    for r in bundle.rules:
        label = r.name or f"{r.client}/{r.match_username or '*'}"
        exists = bool(r.name) and r.name in existing_rules
        items.append(schemas.ImportItem(
            kind="rule", name=label,
            action="update" if exists else "create",
            note=f"AD gate: {r.required_ad_group}" if r.ad_group_check else "",
        ))

    if dry_run:
        return schemas.ImportPlan(
            dry_run=True, applied=False, items=items, problems=[],
            counts=_counts(items, []),
        )

    # --- apply (single transaction) ---
    # Phase 1: target servers (need ids for pool members).
    for t in bundle.target_servers:
        ts = existing_targets.get(t.name)
        if ts is None:
            ts = models.TargetServer(name=t.name, secret=t.secret)
            db.add(ts)
            existing_targets[t.name] = ts
        elif t.secret:
            ts.secret = t.secret
        for f in _TARGET_FIELDS:
            setattr(ts, f, getattr(t, f))
    await db.flush()

    # Phase 2: pools + ordered members.
    for p in bundle.pools:
        pool = existing_pools.get(p.name)
        if pool is None:
            pool = models.HomeServerPool(name=p.name)
            db.add(pool)
            existing_pools[p.name] = pool
        for f in _POOL_FIELDS:
            setattr(pool, f, getattr(p, f))
        await db.flush()
        await crud._set_members(
            db, pool, [existing_targets[m].id for m in p.members]
        )
    await db.flush()

    # Phase 3: clients.
    for c in bundle.clients:
        cl = existing_clients.get(c.name)
        if cl is None:
            cl = models.Client(name=c.name, secret=c.secret)
            db.add(cl)
            existing_clients[c.name] = cl
        elif c.secret:
            cl.secret = c.secret
        for f in _CLIENT_FIELDS:
            setattr(cl, f, getattr(c, f))
    await db.flush()

    # Phase 4: rules (append new ones after existing, preserving bundle order).
    maxpos = (
        await db.execute(select(func.coalesce(func.max(models.Rule.position), 0)))
    ).scalar_one()
    nextpos = int(maxpos)
    for r in bundle.rules:
        rule = existing_rules.get(r.name) if r.name else None
        if rule is None:
            nextpos += 1
            rule = models.Rule(position=nextpos, client_id=existing_clients[r.client].id)
            db.add(rule)
            if r.name:
                existing_rules[r.name] = rule
        rule.client_id = existing_clients[r.client].id
        rule.target_pool_id = (
            existing_pools[r.target_pool].id if r.target_pool else None
        )
        rule.name = r.name
        rule.match_username = r.match_username
        rule.ad_group_check = r.ad_group_check
        rule.required_ad_group = r.required_ad_group
        rule.required_ad_group_dn = r.required_ad_group_dn or (
            await _resolve_dn(db, r.required_ad_group) if r.ad_group_check else ""
        )
        rule.username_normalization = r.username_normalization
        rule.ad_fail_mode = r.ad_fail_mode
        rule.pool_down_fallback = r.pool_down_fallback
        rule.enabled = r.enabled
        rule.note = r.note

    counts = _counts(items, [])
    await crud.log(
        db, "import", "config",
        f"{counts['create']} created, {counts['update']} updated",
    )
    await db.commit()
    return schemas.ImportPlan(
        dry_run=False, applied=True, items=items, problems=[], counts=counts,
    )
