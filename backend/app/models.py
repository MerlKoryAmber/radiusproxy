"""Data model.

These tables are the panel's *own* store. They are rendered into a FreeRADIUS
3.2 proxy.conf on demand. FreeRADIUS itself never reads this database for
proxying — it reads the generated file.

Mapping to proxy.conf:
    TargetServer    -> home_server { ... }   (FR syntax keeps "home_server")
    HomeServerPool  -> home_server_pool { ... }  (ordered members)
    (realm blocks are auto-generated per pool for proxying; routing is chosen
     per Client, not by User-Name — see ADR-0003)
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
from sqlalchemy import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import crypto
from .database import Base


class EncryptedStr(TypeDecorator):
    """Transparently encrypts a string column at rest (Fernet). In Python the
    attribute is cleartext; in the DB it is stored as `enc:<token>`."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return crypto.encrypt(value)

    def process_result_value(self, value, dialect):
        return crypto.decrypt(value)

# FreeRADIUS home_server "type" values we expose (target servers).
# Only "auth+acct" is valid: a proxy `home_server_pool { type = fail-over }`
# routing auth requests rejects a member of any other type — FreeRADIUS `-XC`
# fails with `Unknown home_server "<name>"` and apply is refused. Locking the
# set to the one working value removes that trap (see ADR-0009 verification).
TARGET_SERVER_TYPES = ("auth+acct",)
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


class TargetServer(Base):
    """An upstream RADIUS server we proxy to. Rendered as `home_server {}` in
    proxy.conf (FR syntax). UI/domain name: "target server" (ADR-0003)."""

    __tablename__ = "target_servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    # `name` becomes the identifier in `home_server <name> { }`.
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(16), default="auth")
    ipaddr: Mapped[str] = mapped_column(String(128))  # IPv4/IPv6/hostname
    port: Mapped[int] = mapped_column(Integer, default=1812)
    secret: Mapped[str] = mapped_column(EncryptedStr)  # NAS<->target, encrypted

    # Common tuning knobs (sane FreeRADIUS defaults).
    require_message_authenticator: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    status_check: Mapped[str] = mapped_column(String(16), default="status-server")
    response_window: Mapped[int] = mapped_column(Integer, default=20)
    zombie_period: Mapped[int] = mapped_column(Integer, default=40)
    revive_interval: Mapped[int] = mapped_column(Integer, default=120)
    check_interval: Mapped[int] = mapped_column(Integer, default=30)
    # Successful health pings in a row before a dead server is marked alive
    # again (FreeRADIUS `num_answers_to_alive`). Only used when status_check
    # != none. ADR-0010.
    num_answers_to_alive: Mapped[int] = mapped_column(
        Integer, default=3, server_default="3"
    )

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["PoolMember"]] = relationship(
        back_populates="target_server", cascade="all, delete-orphan"
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
        UniqueConstraint("pool_id", "target_server_id", name="uq_pool_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pool_id: Mapped[int] = mapped_column(
        ForeignKey("home_server_pools.id", ondelete="CASCADE")
    )
    target_server_id: Mapped[int] = mapped_column(
        ForeignKey("target_servers.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    pool: Mapped[HomeServerPool] = relationship(back_populates="members")
    target_server: Mapped[TargetServer] = relationship(back_populates="memberships")


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
    secret: Mapped[str] = mapped_column(EncryptedStr)  # NAS<->proxy, encrypted
    shortname: Mapped[str] = mapped_column(String(64), default="")
    nas_type: Mapped[str] = mapped_column(String(24), default="other")
    proto: Mapped[str] = mapped_column(String(4), default="udp")
    require_message_authenticator: Mapped[str] = mapped_column(
        String(4), default="auto"
    )
    # When on, the srcip policy injects Packet-Src-IP into NAS-IP-Address (if
    # empty) before proxying, so the upstream sees the true originator. Rendered
    # as a custom client{} field read by policy.d/radiuspanel (%{client:...}).
    # NAS-level property: inject Packet-Src-IP into NAS-IP-Address before proxy.
    preserve_source_ip: Mapped[bool] = mapped_column(Boolean, default=False)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Rule(Base):
    """Ordered routing rule (ADR-0004). Evaluated top→bottom, first match wins.

    Match: this client, optionally refined by a username wildcard. Action: proxy
    to `target_pool` and (optionally) require an AD group. Routing/AD-gate live
    here, not on Client. No rule matches → request is rejected (not proxied).
    """

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")

    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE")
    )
    # Empty = match any username for that client; else a wildcard (e.g. *@corp).
    match_username: Mapped[str] = mapped_column(String(256), default="")

    target_pool_id: Mapped[int | None] = mapped_column(
        ForeignKey("home_server_pools.id", ondelete="SET NULL"), nullable=True
    )

    ad_group_check: Mapped[bool] = mapped_column(Boolean, default=False)
    # Group by common name (cn) for humans; DN kept for unambiguous matching.
    required_ad_group: Mapped[str] = mapped_column(String(256), default="")
    required_ad_group_dn: Mapped[str] = mapped_column(String(512), default="")
    username_normalization: Mapped[str] = mapped_column(String(24), default="none")
    ad_fail_mode: Mapped[str] = mapped_column(String(8), default="open")

    # If the target pool is fully down, fall back to checking the 1st factor
    # (AD password, PAP) locally and ACCEPT — a deliberate 2FA bypass on outage.
    # Requires AD/LDAP configured. Off by default.
    pool_down_fallback: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")

    client: Mapped["Client"] = relationship(foreign_keys=[client_id])
    target_pool: Mapped["HomeServerPool | None"] = relationship(
        foreign_keys=[target_pool_id]
    )


class AdGroupCatalog(Base):
    """Catalog of AD groups (cn + DN) synced from AD, for the group autocomplete
    (ADR-0004). Membership lives in AdGroupMember; this is just the name list."""

    __tablename__ = "ad_group_catalog"

    id: Mapped[int] = mapped_column(primary_key=True)
    dn: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    cn: Mapped[str] = mapped_column(String(256), index=True)


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
    bind_password: Mapped[str] = mapped_column(EncryptedStr, default="")

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
    # How often the panel pulls group membership from AD into its own DB (s).
    # The FR gate then compares locally (ADR-0002) — AD outages don't block auth.
    group_sync_interval: Mapped[int] = mapped_column(Integer, default=1800)

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


class AdGroupSync(Base):
    """Per-group sync bookkeeping. One row per required AD group (by DN).

    The panel pulls each gated realm's required group from AD on a schedule and
    records the result here; the members land in AdGroupMember. The FR gate
    reads the members locally, so a failed/stale sync never blocks auth — it
    just means the list is as fresh as `last_synced_at` (ADR-0002).
    """

    __tablename__ = "ad_group_sync"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_dn: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="never")  # never/ok/error
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AdGroupMember(Base):
    """A username known (at last sync) to belong to an AD group.

    The FR `sql` gate looks up (group_dn, username) here. `username` is stored
    lower-cased and normalised (sAMAccountName) to match the gate's lookup.
    """

    __tablename__ = "ad_group_member"
    __table_args__ = (
        UniqueConstraint("group_dn", "username", name="uq_group_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_dn: Mapped[str] = mapped_column(String(512), index=True)
    username: Mapped[str] = mapped_column(String(256), index=True)


class AuthSettings(Base):
    """Singleton (id=1). Panel access controls: login requirement + IP allowlist."""

    __tablename__ = "auth_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Newline/comma-separated IPs or CIDRs allowed to reach /api. Empty = all.
    # Loopback is always allowed (anti-lockout).
    ip_allowlist: Mapped[str] = mapped_column(Text, default="")


class TlsSettings(Base):
    """Singleton (id=1). Panel HTTPS certificate. Key encrypted at rest; both
    are materialised to the shared cert volume that nginx serves."""

    __tablename__ = "tls_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    cert_pem: Mapped[str] = mapped_column(Text, default="")
    key_pem: Mapped[str] = mapped_column(EncryptedStr, default="")
    is_self_signed: Mapped[bool] = mapped_column(Boolean, default=True)


class RadiusSettings(Base):
    """Singleton (id=1). Global FreeRADIUS server tunables the panel patches into
    radiusd.conf on apply. max_request_time also caps a home_server's
    response_window — raise it for slow interactive 2FA (push/OTP approval)."""

    __tablename__ = "radius_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    # Max seconds FreeRADIUS spends on a request. FR default is 30; a target's
    # response_window is clamped to this, so slow 2FA needs a higher value.
    max_request_time: Mapped[int] = mapped_column(Integer, default=30, server_default="30")


class User(Base):
    """Panel admin account. Seeded as admin/admin on first startup (§21
    install-ready) — change the password before enabling auth in production."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProxyDecision(Base):
    """A per-request proxy/gate decision, written by FreeRADIUS via rlm_sql
    (radiuspanel_log policy). The panel reads it for the decision-log screen.

    Populated at runtime by FR, not by the panel API. Fields are what the log
    policy can capture in post-auth/post-proxy.
    """

    __tablename__ = "proxy_decision"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # server_default="" so FreeRADIUS's raw INSERT can omit any of these without
    # tripping NOT NULL (rlm_sql supplies only the columns it captures).
    nas_ip: Mapped[str] = mapped_column(String(64), default="", server_default="''")
    packet_src_ip: Mapped[str] = mapped_column(String(64), default="", server_default="''")
    username: Mapped[str] = mapped_column(String(256), default="", server_default="''", index=True)
    realm: Mapped[str] = mapped_column(String(128), default="", server_default="''", index=True)
    ad_result: Mapped[str] = mapped_column(String(32), default="", server_default="''")  # pass/reject/skip/n-a
    reply: Mapped[str] = mapped_column(String(32), default="", server_default="''")  # Access-Accept/Reject/...
    home_server: Mapped[str] = mapped_column(String(128), default="", server_default="''")


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
