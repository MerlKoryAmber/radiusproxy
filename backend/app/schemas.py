"""Pydantic v2 schemas. Validation here mirrors FreeRADIUS constraints so bad
config is rejected at the API boundary rather than by radiusd later.
"""
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import (
    AD_FAIL_MODES,
    CLIENT_PROTOS,
    MESSAGE_AUTH_MODES,
    NAS_TYPES,
    POOL_TYPES,
    STATUS_CHECK_TYPES,
    TARGET_SERVER_TYPES,
    TLS_REQUIRE_CERT,
    USERNAME_NORMALIZATIONS,
)

_NAME_RE = r"^[A-Za-z0-9_.\-]+$"


# --------------------------- Target servers -------------------------------
class TargetServerBase(BaseModel):
    name: str = Field(pattern=_NAME_RE, max_length=64)
    type: str = "auth"
    ipaddr: str = Field(max_length=128)
    port: int = Field(default=1812, ge=1, le=65535)
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
        if v not in TARGET_SERVER_TYPES:
            raise ValueError(f"type must be one of {TARGET_SERVER_TYPES}")
        return v

    @field_validator("status_check")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in STATUS_CHECK_TYPES:
            raise ValueError(f"status_check must be one of {STATUS_CHECK_TYPES}")
        return v


class TargetServerCreate(TargetServerBase):
    secret: str = Field(min_length=1, max_length=256)


class TargetServerUpdate(TargetServerBase):
    # Empty = keep the stored secret (write-only).
    secret: str = Field(default="", max_length=256)


class TargetServerOut(TargetServerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    has_secret: bool = False


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
    # Ordered list of target server ids that make up the pool.
    member_ids: list[int] = []


class PoolUpdate(PoolBase):
    member_ids: list[int] = []


class PoolMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    target_server_id: int
    position: int
    name: str


class PoolOut(PoolBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    members: list[PoolMemberOut] = []


# --------------------------- Clients (NAS) --------------------------------
class ClientBase(BaseModel):
    name: str = Field(pattern=_NAME_RE, max_length=64)
    ipaddr: str = Field(min_length=1, max_length=64)  # IP or CIDR
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
    secret: str = Field(min_length=1, max_length=256)


class ClientUpdate(ClientBase):
    # Empty = keep the stored secret (write-only).
    secret: str = Field(default="", max_length=256)


class ClientOut(ClientBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    has_secret: bool = False


# --------------------------- Rules (routing) ------------------------------
class RuleBase(BaseModel):
    name: str = Field(default="", max_length=128)
    client_id: int
    match_username: str = Field(default="", max_length=256)  # wildcard, "" = any
    target_pool_id: int | None = None
    ad_group_check: bool = False
    required_ad_group: str = Field(default="", max_length=256)  # cn
    required_ad_group_dn: str = Field(default="", max_length=512)
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


class RuleCreate(RuleBase):
    pass


class RuleUpdate(RuleBase):
    pass


class RuleOut(RuleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    client_name: str | None = None
    target_pool_name: str | None = None


class RuleReorder(BaseModel):
    ids: list[int]  # rule ids in the desired top→bottom order


class AdGroupOut(BaseModel):
    cn: str
    dn: str


# --------------------------- System / access ------------------------------
class AccessSettingsIn(BaseModel):
    ip_allowlist: str = Field(default="", max_length=8192)


class AccessSettingsOut(BaseModel):
    ip_allowlist: str = ""


class TlsReplaceIn(BaseModel):
    cert_pem: str = Field(min_length=1)
    key_pem: str = Field(min_length=1)


class TlsOut(BaseModel):
    has_cert: bool = False
    is_self_signed: bool = True
    subject: str = ""
    issuer: str = ""
    not_after: str = ""


class HostInfoOut(BaseModel):
    hostname: str = ""
    addresses: list[str] = []


class RadiusSettingsIn(BaseModel):
    # FR caps a target's response_window to this; raise for slow interactive 2FA.
    max_request_time: int = Field(default=30, ge=5, le=600)


class RadiusSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    max_request_time: int = 30


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
    # Summary of the stored CA so the UI can confirm which cert is in place
    # (parity with the panel TLS cert). Empty when no/invalid CA.
    ca_subject: str = ""
    ca_not_after: str = ""


# --------------------------- Config ---------------------------------------
class ConfigPreview(BaseModel):
    content: str


class ApplyResponse(BaseModel):
    written_paths: list[str]
    validated: bool
    validation_output: str
    reloaded: bool
    reload_output: str


# --------------------------- Import / export ------------------------------
# Portable bundle: entities reference each other by NAME (not id) so the file
# is human-readable and stable across DBs. Import resolves names → ids.
class ImportTarget(TargetServerBase):
    # Optional on import: required only when creating a new target.
    secret: str = Field(default="", max_length=256)


class ImportPool(PoolBase):
    # Ordered target-server NAMES that make up the pool.
    members: list[str] = []


class ImportClient(ClientBase):
    secret: str = Field(default="", max_length=256)


class ImportRule(BaseModel):
    # Name-based rule (RuleBase is id-based; mirror its fields + validators here).
    name: str = Field(default="", max_length=128)
    client: str = Field(max_length=64)  # client NAME
    match_username: str = Field(default="", max_length=256)
    target_pool: str | None = Field(default=None, max_length=64)  # pool NAME
    ad_group_check: bool = False
    required_ad_group: str = Field(default="", max_length=256)
    required_ad_group_dn: str = Field(default="", max_length=512)
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


class ImportBundle(BaseModel):
    version: int = 1
    source: str = ""
    target_servers: list[ImportTarget] = []
    pools: list[ImportPool] = []
    clients: list[ImportClient] = []
    rules: list[ImportRule] = []


class ImportItem(BaseModel):
    kind: str  # target_server | pool | client | rule
    name: str
    action: str  # create | update
    note: str = ""


class ImportProblem(BaseModel):
    kind: str
    name: str
    error: str


class ImportPlan(BaseModel):
    dry_run: bool
    applied: bool
    items: list[ImportItem] = []
    problems: list[ImportProblem] = []
    counts: dict[str, int] = {}
