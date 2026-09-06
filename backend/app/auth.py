"""Panel auth — stdlib only (pbkdf2 password hashing + HMAC-signed tokens).

Auth is off by default (AuthSettings.enabled). When off, every request passes.
No external crypto deps: passwords use pbkdf2_hmac, tokens are a signed
base64 payload with an expiry.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .config import get_settings
from .database import get_db

settings = get_settings()
_PBKDF2_ROUNDS = 200_000


# --------------------------- passwords ------------------------------------
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2$sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, digest, rounds, salt_hex, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac(
            digest, password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# --------------------------- tokens ---------------------------------------
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(username: str) -> str:
    payload = {"sub": username, "exp": int(time.time()) + settings.auth_token_ttl}
    body = _b64(json.dumps(payload).encode())
    sig = hmac.new(
        settings.jwt_secret.encode(), body.encode(), hashlib.sha256
    ).digest()
    return f"{body}.{_b64(sig)}"


def verify_token(token: str) -> str | None:
    try:
        body, sig = token.split(".")
        expected = hmac.new(
            settings.jwt_secret.encode(), body.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_unb64(sig), expected):
            return None
        payload = json.loads(_unb64(body))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload.get("sub")
    except Exception:
        return None


# --------------------------- seeding / gate -------------------------------
async def ensure_seed(db: AsyncSession) -> None:
    """Create AuthSettings row and a default admin/admin user if missing."""
    if await db.get(models.AuthSettings, 1) is None:
        db.add(models.AuthSettings(id=1, enabled=False))
    count = (
        await db.execute(select(func.count()).select_from(models.User))
    ).scalar_one()
    if not count:
        db.add(
            models.User(username="admin", password_hash=hash_password("admin"))
        )
    await db.commit()


async def auth_enabled(db: AsyncSession) -> bool:
    row = await db.get(models.AuthSettings, 1)
    return bool(row and row.enabled)


async def require_user(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> str | None:
    """FastAPI dependency: when auth is enabled, require a valid Bearer token."""
    if not await auth_enabled(db):
        return None
    token = authorization[7:] if authorization.startswith("Bearer ") else ""
    sub = verify_token(token) if token else None
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    return sub
