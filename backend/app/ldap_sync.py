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


def test_connection(cfg: models.LdapSettings) -> dict:
    """Best-effort connect + bind + one base-DN probe. Never raises — returns a
    structured result the UI shows as pass/fail with a concrete reason. Uses the
    SAVED settings (bind password is write-only)."""
    import time as _time

    t0 = _time.monotonic()

    def _ms() -> int:
        return int((_time.monotonic() - t0) * 1000)

    if not cfg.server:
        return {"ok": False, "stage": "config", "message": "Server host / IP is empty"}

    try:
        conn = _connect(cfg)  # auto_bind → raises on connect/TLS/bind failure
    except Exception as exc:  # noqa: BLE001 — surface the reason, don't crash
        return {
            "ok": False,
            "stage": "bind",
            "message": f"connect/bind failed: {exc}",
            "elapsed_ms": _ms(),
        }

    try:
        base = cfg.base_dn or cfg.group_base_dn or ""
        if base:
            try:
                conn.search(
                    search_base=base,
                    search_filter="(objectClass=*)",
                    search_scope=ldap3.BASE,
                    attributes=["1.1"],
                    size_limit=1,
                )
            except Exception as exc:  # noqa: BLE001
                return {
                    "ok": False,
                    "stage": "search",
                    "bound": True,
                    "message": f"bound OK, but base DN search failed: {exc}",
                    "elapsed_ms": _ms(),
                }
        whoami = ""
        try:
            whoami = conn.extend.standard.who_am_i() or ""
        except Exception:  # noqa: BLE001 — optional, some DCs disallow it
            whoami = ""
        return {
            "ok": True,
            "stage": "ok",
            "bound": True,
            "tls": bool(cfg.use_ldaps or cfg.start_tls),
            "whoami": whoami,
            "message": "Connected and bound successfully"
            + ("" if base else " (no Base DN set — bind only)"),
            "elapsed_ms": _ms(),
        }
    finally:
        try:
            conn.unbind()
        except Exception:  # noqa: BLE001
            pass


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


def fetch_group_catalog(cfg: models.LdapSettings) -> list[tuple[str, str]]:
    """Return (cn, dn) for every group under base_dn — for the autocomplete
    catalog (no membership). Raises on connection/search failure."""
    base = cfg.group_base_dn or cfg.base_dn
    conn = _connect(cfg)
    try:
        out: list[tuple[str, str]] = []
        entries = conn.extend.standard.paged_search(
            search_base=base,
            search_filter="(objectClass=group)",
            search_scope=ldap3.SUBTREE,
            attributes=["cn"],
            paged_size=500,
            generator=True,
        )
        for e in entries:
            dn = e.get("dn")
            cn = (e.get("attributes") or {}).get("cn")
            if isinstance(cn, list):
                cn = cn[0] if cn else None
            if dn and cn:
                out.append((str(cn), str(dn)))
        return out
    finally:
        conn.unbind()


async def sync_all(db: AsyncSession) -> list[dict]:
    """Sync the AD group catalog (for autocomplete) + membership for the groups
    used by rules. Blocking ldap3 runs via asyncio.to_thread; per-group failures
    are recorded and leave the previous members in place (ADR-0002/0004).
    """
    import asyncio

    cfg = await db.get(models.LdapSettings, 1)
    results: list[dict] = []
    if not cfg or not cfg.enabled:
        return results

    # 1) Catalog of all groups (cn+dn) for autocomplete — best-effort.
    try:
        catalog = await asyncio.to_thread(fetch_group_catalog, cfg)
        await db.execute(delete(models.AdGroupCatalog))
        for cn, dn in catalog:
            db.add(models.AdGroupCatalog(cn=cn, dn=dn))
        results.append({"catalog": len(catalog)})
    except Exception as exc:  # noqa: BLE001
        results.append({"catalog": "error", "error": str(exc)})

    # 2) Membership for the groups referenced by rules (by DN).
    wanted = (
        await db.execute(
            select(models.Rule.required_ad_group_dn)
            .where(models.Rule.ad_group_check, models.Rule.enabled)
            .where(models.Rule.required_ad_group_dn != "")
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
