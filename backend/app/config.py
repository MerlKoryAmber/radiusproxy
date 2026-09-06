"""Application settings.

All values are overridable via environment variables so the same image runs
against SQLite in development and PostgreSQL in production.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database -------------------------------------------------------
    # SQLite by default so the panel runs out of the box. In production set
    # DATABASE_URL to something like:
    #   postgresql+asyncpg://radpanel:secret@db:5432/radpanel
    database_url: str = "sqlite+aiosqlite:///./radpanel.db"

    # --- FreeRADIUS integration ----------------------------------------
    # Where the rendered proxy.conf is written. On the FreeRADIUS host this is
    # usually /etc/freeradius/3.0/proxy.conf (Debian) or
    # /etc/raddb/proxy.conf (RHEL). In dev it stays local.
    proxy_conf_path: str = "./generated/proxy.conf"

    # Where the rendered clients.conf is written (the request originators / NAS).
    # On the FreeRADIUS host usually /etc/freeradius/3.0/clients.conf (Debian)
    # or /etc/raddb/clients.conf (RHEL).
    clients_conf_path: str = "./generated/clients.conf"

    # AD/LDAP module (rlm_ldap) and its CA cert. On the FreeRADIUS host these
    # point at mods-enabled/ldap and a readable cert path; in dev they stay
    # local. Written only when AD is enabled in the panel.
    ldap_conf_path: str = "./generated/mods-enabled/ldap"
    ldap_ca_path: str = "./generated/certs/ad-ca.pem"

    # Command used to validate config before applying. `radiusd -XC` (or
    # `freeradius -XC`) does a dry-run parse and exits non-zero on error.
    # Leave empty to skip validation (e.g. when the panel runs off-host).
    radius_check_cmd: str = ""  # e.g. "freeradius -XC"

    # Command used to reload FreeRADIUS after a successful apply.
    # Leave empty to skip the reload (config file is still written).
    radius_reload_cmd: str = ""  # e.g. "systemctl reload freeradius"

    # --- API ------------------------------------------------------------
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
