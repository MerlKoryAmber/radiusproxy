"""Pydantic v2 schemas. Validation here mirrors FreeRADIUS constraints so bad
config is rejected at the API boundary rather than by radiusd later.
"""
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import (
    AD_FAIL_MODES,
    CLIENT_PROTOS,
    HOME_SERVER_TYPES,
    MESSAGE_AUTH_MODES,
    NAS_TYPES,
    POOL_TYPES,
    STATUS_CHECK_TYPES,
    TLS_REQUIRE_CERT,
    USERNAME_NORMALIZATIONS,
)

_NAME_RE = r"^[A-Za-z0-9_.\-]+$"


# --------------------------- Home servers ---------------------------------
class HomeServerBase(BaseModel):
    name: str = Field(pattern=_NAME_RE, max_length=64)
    type: str = "auth"
    ipaddr: str = Field(max_length=128)
    port: int = Field(default=1812, ge=1, le=65535)
    secret: str = Field(min_length=1, max_length=256)
    require_message_authenticator: bool = False
    status_check: str = "status-server"
    response_window: int = Field(default=20, ge=1, le=120)
    zombie_period: int = Field(default=40, ge=1, le=600)
    revive_interval: int = Field(default=120, ge=10, le=3600)
    check_interval: int = Field(default=30, ge=1, le=600)
    enabled: bool = True
    note: str = ""

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in HOME_SERVER_TYPES:
            raise ValueError(f"type must be one of {HOME_SERVER_TYPES}")
        return v

    @field_validator("status_check")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in STATUS_CHECK_TYPES:
            raise ValueError(f"status_check must be one of {STATUS_CHECK_TYPES}")
        return v


class HomeServerCreate(HomeServerBase):
    pass


class HomeServerUpdate(HomeServerBase):
    pass


class HomeServerOut(HomeServerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --------------------------- Pools ----------------------------------------
class PoolBase(BaseModel):
    name: str = Field(pattern=_NAME_RE, max_length=64)
    type: str = "fail-over"
    enabled: bool = True
    note: str = ""

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in POOL_TYPES:
            raise ValueError(f"type must be one of {POOL_TYPES}")
        return v


class PoolCreate(PoolBase):
    # Ordered list of home_server ids that make up the pool.
    member_ids: list[int] = []


class PoolUpdate(PoolBase):
    member_ids: list[int] = []


class PoolMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    home_server_id: int
    position: int
    name: str


class PoolOut(PoolBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    members: list[PoolMemberOut] = []


# --------------------------- Realms ---------------------------------------
class RealmBase(BaseModel):
    name: str = Field(pattern=_NAME_RE, max_length=128)
    auth_pool_id: int | None = None
    acct_pool_id: int | None = None
    nostrip: bool = False
    ad_group_check: bool = False
    required_ad_group: str = Field(default="", max_length=512)
    username_normalization: str = "none"
    ad_fail_mode: str = "open"
    enabled: bool = True
    note: str = ""

    @field_validator("username_normalization")
    @classmethod
    def _valid_norm(cls, v: str) -> str:
        if v not in USERNAME_NORMALIZATIONS:
            raise ValueError(f"must be one of {USERNAME_NORMALIZATIONS}")
        return v

    @field_validator("ad_fail_mode")
    @classmethod
    def _valid_fail(cls, v: str) -> str:
        if v not in AD_FAIL_MODES:
            raise ValueError(f"must be one of {AD_FAIL_MODES}")
        return v


class RealmCreate(RealmBase):
    pass


class RealmUpdate(RealmBase):
    pass


class RealmOut(RealmBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    auth_pool_name: str | None = None
    acct_pool_name: str | None = None


# --------------------------- Clients (NAS) --------------------------------
class ClientBase(BaseModel):
    name: str = Field(pattern=_NAME_RE, max_length=64)
    ipaddr: str = Field(min_length=1, max_length=64)  # IP or CIDR
    secret: str = Field(min_length=1, max_length=256)
    shortname: str = Field(default="", max_length=64)
    nas_type: str = "other"
    proto: str = "udp"
    require_message_authenticator: str = "auto"
    preserve_source_ip: bool = False
    enabled: bool = True
    note: str = ""

    @field_validator("nas_type")
    @classmethod
    def _valid_nas(cls, v: str) -> str:
        if v not in NAS_TYPES:
            raise ValueError(f"nas_type must be one of {NAS_TYPES}")
        return v

    @field_validator("proto")
    @classmethod
    def _valid_proto(cls, v: str) -> str:
        if v not in CLIENT_PROTOS:
            raise ValueError(f"proto must be one of {CLIENT_PROTOS}")
        return v

    @field_validator("require_message_authenticator")
    @classmethod
    def _valid_msgauth(cls, v: str) -> str:
        if v not in MESSAGE_AUTH_MODES:
            raise ValueError(f"must be one of {MESSAGE_AUTH_MODES}")
        return v


class ClientCreate(ClientBase):
    pass


class ClientUpdate(ClientBase):
    pass


class ClientOut(ClientBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --------------------------- LDAP / AD ------------------------------------
class LdapSettingsBase(BaseModel):
    enabled: bool = False
    server: str = Field(default="", max_length=256)
    port: int = Field(default=389, ge=1, le=65535)
    use_ldaps: bool = False
    start_tls: bool = False
    bind_dn: str = Field(default="", max_length=512)
    base_dn: str = Field(default="", max_length=512)
    group_base_dn: str = Field(default="", max_length=512)
    group_filter: str = Field(default="(objectClass=group)", max_length=512)
    group_membership_attribute: str = Field(default="memberOf", max_length=128)
    cache_ttl: int = Field(default=300, ge=0, le=86400)
    net_timeout: int = Field(default=5, ge=1, le=120)
    group_sync_interval: int = Field(default=1800, ge=60, le=86400)
    tls_require_cert: str = "allow"
    tls_min_version: str = Field(default="1.2", max_length=4)

    @field_validator("tls_require_cert")
    @classmethod
    def _valid_reqcert(cls, v: str) -> str:
        if v not in TLS_REQUIRE_CERT:
            raise ValueError(f"must be one of {TLS_REQUIRE_CERT}")
        return v


class LdapSettingsUpdate(LdapSettingsBase):
    # Write-only. Empty string keeps the stored password unchanged.
    bind_password: str = ""
    # CA cert (PEM). Empty string keeps the stored cert; "-" clears it.
    ca_cert: str = ""


class LdapSettingsOut(LdapSettingsBase):
    model_config = ConfigDict(from_attributes=True)
    # Never return the secret; expose only whether one is set.
    has_password: bool = False
    # CA is not secret, but kept out of the list payload; flag + download route.
    has_ca_cert: bool = False


# --------------------------- Config ---------------------------------------
class ConfigPreview(BaseModel):
    content: str


class ApplyResponse(BaseModel):
    written_paths: list[str]
    validated: bool
    validation_output: str
    reloaded: bool
    reload_output: str
