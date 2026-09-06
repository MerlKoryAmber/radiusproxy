"""Pull AD group membership into the panel's own DB (ADR-0002).

The gate compares locally against these rows, so an AD outage never blocks auth
— the list is only as stale as the last successful sync. ldap3 is synchronous;
callers run this via asyncio.to_thread.
"""
from __future__ import annotations

from datetime import datetime, timezone

import ldap3
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models

# AD "member of (including nested)" matching rule OID.
_IN_CHAIN = "1.2.840.113556.1.4.1941"


def _connect(cfg: models.LdapSettings) -> ldap3.Connection:
    tls = None
    if cfg.use_ldaps or cfg.start_tls:
        tls = ldap3.Tls(
            ca_certs_data=cfg.ca_cert or None,
            validate=(
                __import__("ssl").CERT_REQUIRED
                if cfg.tls_require_cert in ("demand", "hard") and cfg.ca_cert.strip()
                else __import__("ssl").CERT_NONE
            ),
        )
    server = ldap3.Server(
        cfg.server,
        port=cfg.port or (636 if cfg.use_ldaps else 389),
        use_ssl=cfg.use_ldaps,
        tls=tls,
        connect_timeout=cfg.net_timeout,
    )
    conn = ldap3.Connection(
        server,
        user=cfg.bind_dn or None,
        password=cfg.bind_password or None,
        auto_bind=(
            ldap3.AUTO_BIND_TLS_BEFORE_BIND if cfg.start_tls else ldap3.AUTO_BIND_NO_TLS
        ),
        receive_timeout=cfg.net_timeout,
    )
    return conn


def fetch_group_members(cfg: models.LdapSettings, group_dn: str) -> set[str]:
    """Return the sAMAccountNames (lower-cased) that belong to group_dn,
    including nested membership. Raises on connection/search failure."""
    base = cfg.group_base_dn or cfg.base_dn
    flt = f"(&(objectClass=user)(memberOf:{_IN_CHAIN}:={group_dn}))"
    conn = _connect(cfg)
    try:
        members: set[str] = set()
        entries = conn.extend.standard.paged_search(
            search_base=base,
            search_filter=flt,
            search_scope=ldap3.SUBTREE,
            attributes=["sAMAccountName"],
            paged_size=500,
            generator=True,
        )
        for e in entries:
            attrs = e.get("attributes") or {}
            sam = attrs.get("sAMAccountName")
            if isinstance(sam, list):
                sam = sam[0] if sam else None
            if sam:
                members.add(str(sam).lower())
        return members
    finally:
        conn.unbind()


def _required_groups(db_sync_rows: list[str]) -> list[str]:  # pragma: no cover
    return db_sync_rows


async def sync_all(db: AsyncSession) -> list[dict]:
    """Sync every gated realm's required group. Returns per-group results.

    Uses asyncio.to_thread for the blocking ldap3 calls. Failures are recorded
    per group (status=error) and leave the previously-synced members in place.
    """
    import asyncio

    cfg = await db.get(models.LdapSettings, 1)
    results: list[dict] = []
    if not cfg or not cfg.enabled:
        return results

    wanted = (
        await db.execute(
            select(models.Client.required_ad_group)
            .where(models.Client.ad_group_check, models.Client.enabled)
            .where(models.Client.required_ad_group != "")
        )
    ).scalars().all()
    groups = sorted({g for g in wanted if g})

    for group_dn in groups:
        row = (
            await db.execute(
                select(models.AdGroupSync).where(
                    models.AdGroupSync.group_dn == group_dn
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = models.AdGroupSync(group_dn=group_dn)
            db.add(row)
            await db.flush()

        try:
            members = await asyncio.to_thread(fetch_group_members, cfg, group_dn)
            # Replace this group's members atomically.
            await db.execute(
                delete(models.AdGroupMember).where(
                    models.AdGroupMember.group_dn == group_dn
                )
            )
            for username in members:
                db.add(
                    models.AdGroupMember(group_dn=group_dn, username=username)
                )
            row.status = "ok"
            row.member_count = len(members)
            row.error = ""
            row.last_synced_at = datetime.now(timezone.utc)
            results.append({"group_dn": group_dn, "status": "ok", "members": len(members)})
        except Exception as exc:  # AD unreachable / bind fail / etc — keep old list
            row.status = "error"
            row.error = str(exc)[:1000]
            row.last_synced_at = datetime.now(timezone.utc)
            results.append({"group_dn": group_dn, "status": "error", "error": str(exc)})

    await db.commit()
    return results
