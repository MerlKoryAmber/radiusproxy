"""Panel TLS certificate helpers (self-signed generation + validation).

The cert/key live in the DB (TlsSettings; key encrypted) and are materialised
to a shared volume that the frontend nginx reads. nginx auto-reloads on change.
"""
from __future__ import annotations

import datetime
import ipaddress
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERT_FILE = "cert.pem"
KEY_FILE = "key.pem"


def generate_self_signed(common_name: str = "radius-proxy-panel") -> tuple[str, str]:
    """Return (cert_pem, key_pem) for a fresh 10-year self-signed RSA cert."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False
        )
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    return cert_pem, key_pem


def validate(cert_pem: str, key_pem: str) -> dict:
    """Validate a cert+key pair; return summary {subject, not_after}. Raises
    ValueError on bad PEM or if the key doesn't match the cert."""
    try:
        cert = x509.load_pem_x509_certificate(cert_pem.encode())
        key = serialization.load_pem_private_key(key_pem.encode(), password=None)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid PEM: {exc}") from exc
    if cert.public_key().public_numbers() != key.public_key().public_numbers():
        raise ValueError("private key does not match the certificate")
    try:
        subject = cert.subject.rfc4514_string()
    except Exception:  # noqa: BLE001
        subject = ""
    return {"subject": subject, "not_after": cert.not_valid_after_utc.isoformat()}


def cert_summary(cert_pem: str) -> dict:
    try:
        cert = x509.load_pem_x509_certificate(cert_pem.encode())
        return {
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "not_after": cert.not_valid_after_utc.isoformat(),
        }
    except Exception:  # noqa: BLE001
        return {}


def write_files(cert_dir: str, cert_pem: str, key_pem: str) -> None:
    d = Path(cert_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / CERT_FILE).write_text(cert_pem)
    kp = d / KEY_FILE
    kp.write_text(key_pem)
    os.chmod(kp, 0o600)


def host_addresses() -> list[str]:
    """Host IPs, best-effort. Set by install.sh into HOST_ADDRESSES (the panel
    runs in a bridged container and cannot see host interfaces itself)."""
    raw = os.environ.get("HOST_ADDRESSES", "")
    out = []
    for part in raw.replace(",", " ").split():
        try:
            ipaddress.ip_address(part)
            out.append(part)
        except ValueError:
            continue
    return out
