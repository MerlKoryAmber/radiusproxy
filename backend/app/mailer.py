"""Outgoing SMTP + the 2FA pool-down fallback alert (ADR-0011).

Two parts:
  * `send_mail` — thin SMTP sender honouring MailSettings (none/starttls/ssl,
    optional auth, comma-separated recipients).
  * `pool_down_watch` — a background loop that tails FreeRADIUS's log for the
    "failing over to fallback radiuspanel_fallback" warning. When a pool goes
    into fallback (2FA bypass becomes active for it) it emails the operator once
    per outage: which pool died, which rules that activates, for whom, and why.

The fallover decision lives inside FreeRADIUS, so the panel learns of it from
the log line rather than being in the request path. De-dup is per-pool: one mail
per outage; a pool must be seen healthy again before it re-alerts.
"""
from __future__ import annotations

import asyncio
import os
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal

settings = get_settings()

# "... : Warning: Home server pool <NAME> failing over to fallback radiuspanel_fallback"
_FALLOVER = re.compile(
    r"Home server pool (\S+) failing over to fallback radiuspanel_fallback"
)


def _recipients(raw: str) -> list[str]:
    return [a.strip() for a in (raw or "").replace(";", ",").split(",") if a.strip()]


def send_mail(cfg, subject: str, body: str, to_override: str = "") -> None:
    """Send one plaintext mail using MailSettings `cfg`. Raises on failure so
    callers (the test endpoint) can surface the real SMTP error."""
    recipients = _recipients(to_override) or _recipients(cfg.to_addrs)
    if not cfg.host or not cfg.from_addr or not recipients:
        raise ValueError("mail not configured: need host, from and recipients")

    msg = EmailMessage()
    msg["From"] = cfg.from_addr
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)

    timeout = 15
    if cfg.security == "ssl":
        server = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=timeout,
                                  context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(cfg.host, cfg.port, timeout=timeout)
    try:
        server.ehlo()
        if cfg.security == "starttls":
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
        if cfg.username:
            server.login(cfg.username, cfg.password or "")
        server.send_message(msg, from_addr=cfg.from_addr, to_addrs=recipients)
    finally:
        try:
            server.quit()
        except Exception:  # noqa: BLE001
            pass


async def _rules_for_pool(db, pool_name: str):
    """Enabled fallback rules routing to `pool_name` — who the bypass affects."""
    from . import models

    rows = (
        await db.execute(
            select(models.Rule)
            .join(models.HomeServerPool,
                  models.Rule.target_pool_id == models.HomeServerPool.id)
            .where(
                models.Rule.enabled,
                models.Rule.pool_down_fallback,
                models.HomeServerPool.name == pool_name,
            )
        )
    ).scalars().all()
    out = []
    for r in rows:
        client = await db.get(models.Client, r.client_id) if r.client_id else None
        out.append({
            "rule": r.name or f"#{r.id}",
            "client": client.name if client else "?",
            "username": r.match_username or "любой",
        })
    return out


def _alert_body(pool_name: str, rules: list[dict], when: str) -> str:
    lines = [
        "ВНИМАНИЕ: включён аварийный обход 2FA (проверка только пароля AD).",
        "",
        f"Время: {when}",
        f"Причина: целевой пул 2FA «{pool_name}» полностью недоступен —",
        "FreeRADIUS переключился на резервную проверку 1-го фактора (пароль в AD).",
        "",
        "На кого распространяется (активные правила с обходом):",
    ]
    if rules:
        for r in rules:
            lines.append(
                f"  • правило «{r['rule']}» — клиент {r['client']}, "
                f"пользователи: {r['username']}"
            )
    else:
        lines.append("  • (правила не найдены — проверьте настройки)")
    lines += [
        "",
        "Пока пул недоступен, вход выполняется по одному фактору. Эти входы",
        "помечаются в панели (Logs) меткой pool-down-1fa.",
        "",
        "— FreeRADIUS Proxy Panel",
    ]
    return "\n".join(lines)


def _tail_new(path: str, pos: int) -> tuple[list[str], int]:
    """Read lines appended since byte offset `pos`. Returns (lines, new_pos).
    Handles truncation/rotation by resetting to 0 when the file shrank."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return [], pos
    if size < pos:  # rotated/truncated
        pos = 0
    if size == pos:
        return [], pos
    try:
        with open(path, "rb") as f:
            f.seek(pos)
            data = f.read()
        return data.decode("utf-8", "replace").splitlines(), size
    except OSError:
        return [], pos


async def pool_down_watch() -> None:
    """Background loop: watch the FR log; on a pool's first fallover, email the
    operator. De-dup per pool until the pool is seen healthy again.

    We start reading at the current end of the log so a restart doesn't re-alert
    on old outages. Errors never kill the loop."""
    from . import models

    path = settings.radius_log_path
    try:
        pos = os.path.getsize(path)
    except OSError:
        pos = 0
    alerted: set[str] = set()  # pools already alerted this outage
    # "... Marking home server ... alive again" clears the outage for re-alert.
    revive = re.compile(r"Marking home server .* alive again")

    while True:
        await asyncio.sleep(15)
        try:
            lines, pos = _tail_new(path, pos)
            if not lines:
                continue
            down_pools: list[str] = []
            saw_revive = False
            for ln in lines:
                m = _FALLOVER.search(ln)
                if m and m.group(1) not in alerted:
                    down_pools.append(m.group(1))
                if revive.search(ln):
                    saw_revive = True
            if saw_revive:
                alerted.clear()  # a server came back — allow future alerts
            if not down_pools:
                continue
            async with SessionLocal() as db:
                cfg = await db.get(models.MailSettings, 1)
                if not (cfg and cfg.enabled):
                    # feature off; still mark so we don't spam once enabled mid-outage
                    alerted.update(down_pools)
                    continue
                when = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
                for pool_name in dict.fromkeys(down_pools):  # unique, ordered
                    rules = await _rules_for_pool(db, pool_name)
                    try:
                        send_mail(
                            cfg,
                            subject=f"[RADIUS] Обход 2FA включён — пул «{pool_name}» недоступен",
                            body=_alert_body(pool_name, rules, when),
                        )
                        alerted.add(pool_name)
                    except Exception:  # noqa: BLE001 — retry next cycle
                        pass
        except Exception:  # noqa: BLE001 — loop must survive any failure
            pass
