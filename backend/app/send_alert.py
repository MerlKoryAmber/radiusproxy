"""CLI to send one alert email using the panel's stored SMTP settings.

Invoked by the host watchdog (`rpp watchdog`) which lives outside the
containers and cannot reach the panel API — it shells into the backend
container instead:

    python -m app.send_alert "<subject>" < body-on-stdin

Reads MailSettings from the DB and reuses `mailer.send_mail`. Exits non-zero
(with a short reason on stderr) if mail is disabled or unconfigured, so the
watchdog can fall back to a host MTA or just record state. Body comes from
stdin so the caller need not quote a multi-line message.
"""
from __future__ import annotations

import asyncio
import sys


async def _main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m app.send_alert <subject>  (body on stdin)", file=sys.stderr)
        return 2
    subject = sys.argv[1]
    body = sys.stdin.read().strip() or subject

    from .database import SessionLocal
    from . import models
    from .mailer import send_mail

    async with SessionLocal() as db:
        cfg = await db.get(models.MailSettings, 1)
        if not cfg or not cfg.enabled:
            print("mail disabled or not configured", file=sys.stderr)
            return 1
    try:
        # send_mail is blocking (smtplib); run it off the event loop.
        await asyncio.to_thread(send_mail, cfg, subject, body)
    except Exception as exc:  # noqa: BLE001 — report reason, let caller fall back
        print(f"send failed: {exc}", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
