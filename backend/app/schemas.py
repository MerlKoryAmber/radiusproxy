"""Pydantic v2 schemas. Validation here mirrors FreeRADIUS constraints so bad
config is rejected at the API boundary rather than by radiusd later.
"""
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import HOME_SERVER_TYPES, POOL_TYPES, STATUS_CHECK_TYPES

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
    enabled: bool = True
    note: str = ""


class RealmCreate(RealmBase):
    pass


class RealmUpdate(RealmBase):
    pass


class RealmOut(RealmBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    auth_pool_name: str | None = None
    acct_pool_name: str | None = None


# --------------------------- Config ---------------------------------------
class ConfigPreview(BaseModel):
    content: str


class ApplyResponse(BaseModel):
    written_path: str
    validated: bool
    validation_output: str
    reloaded: bool
    reload_output: str
