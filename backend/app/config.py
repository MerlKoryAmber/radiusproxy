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

    # policy.d snippet with the panel's named policies (radiuspanel_srcip/_adgate).
    policy_conf_path: str = "./generated/policy.d/radiuspanel"

    # FR sql module (rlm_sql_postgresql) — the AD gate queries the panel's own
    # Postgres for local group membership. Points at the same DB as the panel.
    sql_conf_path: str = "./generated/mods-enabled/sql"
    sql_db_host: str = "db"
    sql_db_port: int = 5432
    sql_db_login: str = "radpanel"
    sql_db_password: str = "radpanel"
    sql_db_name: str = "radpanel"

    # Command used to validate config before applying. `radiusd -XC` (or
    # `freeradius -XC`) does a dry-run parse and exits non-zero on error.
    # Leave empty to skip validation (e.g. when the panel runs off-host).
    radius_check_cmd: str = ""  # e.g. "freeradius -XC"

    # Command used to reload FreeRADIUS after a successful apply.
    # Leave empty to skip the reload (config file is still written).
    radius_reload_cmd: str = ""  # e.g. "systemctl reload freeradius"

    # FreeRADIUS's own log file — surfaced read-only in the web (Logs → Server log)
    # so unknown-client drops / bad secrets / auth results are visible without SSH.
    radius_log_path: str = "/var/log/freeradius/radius.log"

    # Main FreeRADIUS config — the panel patches only max_request_time in it on
    # apply (from RadiusSettings). Empty/missing = skip (dev without a real raddb).
    radiusd_conf_path: str = "/etc/freeradius/3.0/radiusd.conf"

    # Virtual server for the 2FA pool-down fallback (ADR-0009). Written only when
    # a rule enables it + AD is on; removed otherwise.
    fallback_site_path: str = "/etc/freeradius/3.0/sites-enabled/radiuspanel-fallback"

    # --- Auth (panel login) ---------------------------------------------
    # Signs session tokens. CHANGE in production (env JWT_SECRET). Auth is
    # off by default (toggle stored in the DB) — see AuthSettings.
    jwt_secret: str = "dev-insecure-change-me"
    auth_token_ttl: int = 28800  # seconds (8h)

    # --- Secret encryption at rest --------------------------------------
    # Encrypts shared secrets / bind password stored in the DB (Fernet, derived
    # from this key). CHANGE in production via env APP_ENCRYPTION_KEY. If it
    # changes, previously-encrypted secrets can no longer be decrypted.
    app_encryption_key: str = "dev-insecure-change-me"

    # Panel TLS cert/key are written here (shared volume the frontend nginx reads).
    tls_cert_dir: str = "/certs"

    # --- API ------------------------------------------------------------
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
