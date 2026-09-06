"""Data model.

These tables are the panel's *own* store. They are rendered into a FreeRADIUS
3.2 proxy.conf on demand. FreeRADIUS itself never reads this database for
proxying — it reads the generated file.

Mapping to proxy.conf:
    HomeServer      -> home_server { ... }
    HomeServerPool  -> home_server_pool { ... }  (ordered members)
    Realm           -> realm { ... }
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# FreeRADIUS home_server "type" values we expose.
HOME_SERVER_TYPES = ("auth", "acct", "auth+acct", "coa")
# home_server_pool "type" (load-balancing strategy) values.
POOL_TYPES = (
    "fail-over",
    "load-balance",
    "client-balance",
    "client-port-balance",
    "keyed-balance",
)
# status_check strategies.
STATUS_CHECK_TYPES = ("none", "status-server", "request")
# clients.conf `nas_type` (affects status-check dictionary). "other" is safe.
NAS_TYPES = ("other", "cisco", "juniper", "mikrotik", "aruba", "ruckus")
# clients.conf `proto`.
CLIENT_PROTOS = ("udp", "tcp", "*")
# require_message_authenticator tri-state (RFC 5080 / BlastRADIUS mitigation).
MESSAGE_AUTH_MODES = ("no", "yes", "auto")
# How the incoming User-Name is normalised before the AD lookup.
#   none          -> use User-Name as received
#   strip_realm   -> "user@realm"  -> "user"
#   strip_ntdomain-> "DOMAIN\\user" -> "user"
USERNAME_NORMALIZATIONS = ("none", "strip_realm", "strip_ntdomain")
# What to do when AD is unreachable during the group check (ADR-0001).
AD_FAIL_MODES = ("open", "closed")
# rlm_ldap tls { require_cert } — how strictly the DC cert is validated.
TLS_REQUIRE_CERT = ("never", "allow", "try", "demand", "hard")


class HomeServer(Base):
    __tablename__ = "home_servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    # `name` becomes the identifier in `home_server <name> { }`.
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(16), default="auth")
    ipaddr: Mapped[str] = mapped_column(String(128))  # IPv4/IPv6/hostname
    port: Mapped[int] = mapped_column(Integer, default=1812)
    secret: Mapped[str] = mapped_column(String(256))

    # Common tuning knobs (sane FreeRADIUS defaults).
    require_message_authenticator: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    status_check: Mapped[str] = mapped_column(String(16), default="status-server")
    response_window: Mapped[int] = mapped_column(Integer, default=20)
    zombie_period: Mapped[int] = mapped_column(Integer, default=40)
    revive_interval: Mapped[int] = mapped_column(Integer, default=120)
    check_interval: Mapped[int] = mapped_column(Integer, default=30)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["PoolMember"]] = relationship(
        back_populates="home_server", cascade="all, delete-orphan"
    )


class HomeServerPool(Base):
    __tablename__ = "home_server_pools"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(24), default="fail-over")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    members: Mapped[list["PoolMember"]] = relationship(
        back_populates="pool",
        cascade="all, delete-orphan",
        order_by="PoolMember.position",
    )


class PoolMember(Base):
    """Ordered membership of a home_server in a pool.

    Order matters for fail-over pools (first listed = primary).
    """

    __tablename__ = "pool_members"
    __table_args__ = (
        UniqueConstraint("pool_id", "home_server_id", name="uq_pool_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pool_id: Mapped[int] = mapped_column(
        ForeignKey("home_server_pools.id", ondelete="CASCADE")
    )
    home_server_id: Mapped[int] = mapped_column(
        ForeignKey("home_servers.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    pool: Mapped[HomeServerPool] = relationship(back_populates="members")
    home_server: Mapped[HomeServer] = relationship(back_populates="memberships")


class Realm(Base):
    __tablename__ = "realms"

    id: Mapped[int] = mapped_column(primary_key=True)
    # `name` is the realm suffix, e.g. "example.com" or DEFAULT / NULL.
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)

    # A realm points at a pool for auth and/or acct. When acct_pool is null
    # and auth_pool is set, we render a single `pool = <auth_pool>`.
    auth_pool_id: Mapped[int | None] = mapped_column(
        ForeignKey("home_server_pools.id", ondelete="SET NULL"), nullable=True
    )
    acct_pool_id: Mapped[int | None] = mapped_column(
        ForeignKey("home_server_pools.id", ondelete="SET NULL"), nullable=True
    )

    # If true, keep the realm suffix on the User-Name when proxying.
    nostrip: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- AD group gate (ADR-0001) -----------------------------------------
    # When ad_group_check is on, the proxy checks that the request's user is a
    # member of `required_ad_group` in AD *before* proxying this realm. The
    # group is per realm. Uses the global LdapSettings connection.
    ad_group_check: Mapped[bool] = mapped_column(Boolean, default=False)
    required_ad_group: Mapped[str] = mapped_column(String(512), default="")
    username_normalization: Mapped[str] = mapped_column(
        String(24), default="none"
    )
    # Per-realm override of the AD-unreachable behaviour. "open" = proxy anyway
    # (default, ADR-0001), "closed" = reject when AD is down.
    ad_fail_mode: Mapped[str] = mapped_column(String(8), default="open")

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    auth_pool: Mapped[HomeServerPool | None] = relationship(
        foreign_keys=[auth_pool_id]
    )
    acct_pool: Mapped[HomeServerPool | None] = relationship(
        foreign_keys=[acct_pool_id]
    )


class Client(Base):
    """A RADIUS client (NAS) allowed to send requests to us — the "from whom".

    Rendered into FreeRADIUS `clients.conf` as a `client <name> { ... }` block.
    These are the request originators: VMware UAG, VPN servers, WiFi controllers.
    A request from an IP with no matching client is dropped by FreeRADIUS.
    The shared secret here is NAS<->proxy, separate from the home_server secret.
    """

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # ipaddr accepts a single IPv4/IPv6 or a CIDR (e.g. 10.0.5.0/24).
    ipaddr: Mapped[str] = mapped_column(String(64))
    secret: Mapped[str] = mapped_column(String(256))
    shortname: Mapped[str] = mapped_column(String(64), default="")
    nas_type: Mapped[str] = mapped_column(String(24), default="other")
    proto: Mapped[str] = mapped_column(String(4), default="udp")
    require_message_authenticator: Mapped[str] = mapped_column(
        String(4), default="auto"
    )

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LdapSettings(Base):
    """Global AD/LDAP connection used for the per-realm group gate.

    Singleton: one row (id=1). Rendered into a FreeRADIUS `mods-enabled/ldap`
    module. The bind password is a secret — it is never returned by the API and
    never written to the audit log. NOTE (tail): stored plaintext for MVP; must
    be encrypted at rest before production (see docs/adr/0001).
    """

    __tablename__ = "ldap_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    server: Mapped[str] = mapped_column(String(256), default="")  # host/IP
    port: Mapped[int] = mapped_column(Integer, default=389)
    use_ldaps: Mapped[bool] = mapped_column(Boolean, default=False)  # ldaps:// 636
    start_tls: Mapped[bool] = mapped_column(Boolean, default=False)

    # Bind (service) account used to search AD.
    bind_dn: Mapped[str] = mapped_column(String(512), default="")
    bind_password: Mapped[str] = mapped_column(String(512), default="")

    base_dn: Mapped[str] = mapped_column(String(512), default="")

    # Group membership lookup knobs (rlm_ldap `group {}` sub-section).
    group_base_dn: Mapped[str] = mapped_column(String(512), default="")
    group_filter: Mapped[str] = mapped_column(
        String(512), default="(objectClass=group)"
    )
    # AD stores membership on the user via memberOf; this is the attribute the
    # group check compares against.
    group_membership_attribute: Mapped[str] = mapped_column(
        String(128), default="memberOf"
    )

    # Cache membership to avoid an AD hit on every packet (seconds).
    cache_ttl: Mapped[int] = mapped_column(Integer, default=300)
    net_timeout: Mapped[int] = mapped_column(Integer, default=5)

    # --- TLS (LDAPS / StartTLS) -------------------------------------------
    # Root/CA certificate (PEM) that signed the DC cert. Without it LDAPS
    # usually fails validation. Not a secret — may be shown/downloaded.
    ca_cert: Mapped[str] = mapped_column(Text, default="")
    # How strictly to validate the DC cert against ca_cert. "never" skips
    # validation entirely (works but insecure — diagnostics only).
    tls_require_cert: Mapped[str] = mapped_column(String(8), default="allow")
    tls_min_version: Mapped[str] = mapped_column(String(4), default="1.2")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    """Who changed what, and when. Also records config applies."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(128), default="system")
    action: Mapped[str] = mapped_column(String(64))  # create/update/delete/apply
    entity: Mapped[str] = mapped_column(String(64))  # home_server/pool/realm/config
    entity_ref: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
