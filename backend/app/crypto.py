"""Reversible encryption for secrets stored at rest (ADR: secret-at-rest).

Shared secrets and the AD bind password must be rendered back into FreeRADIUS
config in cleartext, so they can't be one-way hashed — they are encrypted with
Fernet (AES-128-CBC + HMAC) using a key derived from APP_ENCRYPTION_KEY.

Stored form is `enc:<token>`. Values without that prefix are treated as legacy
cleartext and returned as-is, so pre-existing rows keep working.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings

_PREFIX = "enc:"


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().app_encryption_key.encode()
    # Any string → a valid 32-byte urlsafe-base64 Fernet key.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key).digest()))


def encrypt(value: str | None) -> str | None:
    if not value:  # None or "" stored as-is (empty = "no secret")
        return value
    if value.startswith(_PREFIX):  # already encrypted
        return value
    return _PREFIX + _fernet().encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    if not value or not value.startswith(_PREFIX):
        return value  # legacy cleartext or empty
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode()).decode()
    except InvalidToken:
        return value  # wrong key — leave as-is rather than crash
