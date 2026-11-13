"""Internal self-diagnostics (ADR-0012).

A background loop that watches the things a container restart can't fix and the
external watchdog can't see: whether every member of a pool is unreachable,
whether the local FreeRADIUS daemon is alive, and whether the AD/LDAP DC is
reachable while AD is enabled.

It keeps the latest result in memory (read by the dashboard for a banner) and
emails on transitions healthy→problem (deduped per issue key), reusing
`mailer.send_mail`. It never restarts anything itself — "all targets down" is
an external-service outage, not a stack fault; a dead FR daemon is flagged for
the host watchdog to restart the container.
"""
from __future__ import annotations

import asyncio
import os
import re
import socket
import subprocess
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .config import get_settings

# Latest snapshot, read by routers/dashboard.py. Empty `issues` = healthy.
_status: dict = {"checked_at": None, "issues": [], "ok": True}

# Target health = FreeRADIUS's own verdict (ADR-0010), NOT a probe of ours.
# RADIUS is UDP: a TCP connect to :1812 always fails on a live 2FA server, and a
# bare UDP packet proves nothing without a valid request + secret. FR already
# tracks every home_server (status_check pings / real-traffic timeouts) and logs
# each state change by IP:port, e.g.
#   Proxy: Marking home server 172.26.13.229 port 1812 as dead.
#   Proxy: Marking home server 172.26.13.229 port 1812 as zombie (...)
#   Proxy: Marking home server 172.26.13.229 port 1812 alive again...
_HS_MARK = re.compile(r"Marking home server (\S+) port (\d+) (?:as )?(dead|zombie|alive)")
# FR (re)start → every home_server starts alive in FR's memory; drop old verdicts.
_FR_READY = re.compile(r"Ready to process requests")
_SEED_BYTES = 4 * 1024 * 1024  # on first read, scan recent history only

_hs_state: dict[tuple[str, int], str] = {}  # (ip, port) -> dead|zombie|alive
_log_pos: int | None = None


def _update_hs_state() -> None:
    """Advance through radius.log and keep FR's latest verdict per home server.
    Unknown (no event seen) = treated as up: we only report what FR concluded."""
    global _log_pos
    path = get_settings().radius_log_path
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if _log_pos is None:
        start = max(0, size - _SEED_BYTES)
    elif size < _log_pos:  # rotated/truncated (logrotate copytruncate, ADR-0013)
        start = 0
    else:
        start = _log_pos
    if size == start:
        _log_pos = size
        return
    try:
        with open(path, "rb") as f:
            f.seek(start)
            data = f.read()
    except OSError:
        return
    _log_pos = start + len(data)
    for line in data.decode("utf-8", "replace").splitlines():
        if _FR_READY.search(line):
            _hs_state.clear()
            continue
        m = _HS_MARK.search(line)
        if m:
            _hs_state[(m.group(1), int(m.group(2)))] = m.group(3)


def snapshot() -> dict:
    return dict(_status)


def _fr_running() -> bool:
    try:
        return subprocess.run(
            ["pgrep", "-x", "freeradius"], stdout=subprocess.DEVNULL
        ).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _tcp_reachable(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:  # noqa: BLE001
        return False


async def _collect_issues(db) -> list[dict]:
    """Return current problems as [{key, severity, message}]. Cheap checks only."""
    from . import models

    issues: list[dict] = []

    # 1) FreeRADIUS daemon down (host watchdog can restart the container).
    if not await asyncio.to_thread(_fr_running):
        issues.append({
            "key": "fr-down",
            "severity": "critical",
            "message": "FreeRADIUS daemon is not running in the backend container.",
        })

    # 2) FreeRADIUS marked every enabled member of a pool dead (external 2FA
    #    outage). Source: radius.log state changes — see _update_hs_state.
    await asyncio.to_thread(_update_hs_state)
    pools = (
        await db.execute(
            select(models.HomeServerPool)
            .where(models.HomeServerPool.enabled)
            .options(
                selectinload(models.HomeServerPool.members)
                .selectinload(models.PoolMember.target_server)
            )
        )
    ).scalars().all()
    for pool in pools:
        members = [
            m.target_server for m in pool.members
            if m.target_server and m.target_server.enabled
        ]
        if not members:
            continue
        if all(_hs_state.get((t.ipaddr, t.port)) == "dead" for t in members):
            issues.append({
                "key": f"pool-down:{pool.name}",
                "severity": "critical",
                "message": (
                    f"FreeRADIUS marked all targets of pool '{pool.name}' dead "
                    f"({', '.join(f'{t.ipaddr}:{t.port}' for t in members)})."
                ),
            })

    # 3) AD/LDAP DC unreachable while AD is enabled.
    ldap = await db.get(models.LdapSettings, 1)
    if ldap and ldap.enabled and ldap.server:
        if not await asyncio.to_thread(_tcp_reachable, ldap.server, ldap.port):
            issues.append({
                "key": "dc-down",
                "severity": "warning",
                "message": (
                    f"AD/LDAP server {ldap.server}:{ldap.port} is unreachable — "
                    "group checks and the 2FA-bypass fallback will not work."
                ),
            })

    return issues


async def diagnostics_watch() -> None:
    """Loop: refresh the snapshot every ~30s; email on new issues (deduped)."""
    from .database import SessionLocal
    from . import models
    from .mailer import send_mail

    alerted: set[str] = set()

    while True:
        await asyncio.sleep(30)
        try:
            async with SessionLocal() as db:
                issues = await _collect_issues(db)
                _status["issues"] = issues
                _status["ok"] = not issues
                _status["checked_at"] = datetime.now(timezone.utc).isoformat()

                keys = {i["key"] for i in issues}
                # Clear alert-dedup for issues that resolved.
                alerted &= keys
                new = [i for i in issues if i["key"] not in alerted]
                if not new:
                    continue
                cfg = await db.get(models.MailSettings, 1)
                if not (cfg and cfg.enabled):
                    alerted |= keys  # don't spam once enabled mid-incident
                    continue
                when = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
                body = "Panel self-diagnostics detected new issue(s):\n\n" + "\n".join(
                    f"  • [{i['severity']}] {i['message']}" for i in new
                ) + f"\n\nTime: {when}\n— MK RadiusProxy"
                try:
                    await asyncio.to_thread(
                        send_mail, cfg,
                        "[RADIUS] Self-diagnostics alert", body,
                    )
                    alerted |= {i["key"] for i in new}
                except Exception:  # noqa: BLE001 — retry next cycle
                    pass
        except Exception:  # noqa: BLE001 — loop must survive any failure
            pass
