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
