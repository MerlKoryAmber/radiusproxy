# SKELETON — карта проекта

Актуальная структурная карта, чтобы **сверяться, а не перечитывать весь код**.
Обновлять **перед каждым push** (см. §22 CLAUDE.md). Читать после handoff и перед
началом задачи. Если что-то тут расходится с кодом — код прав, а скелет чинить.

**Обновлено:** 2026-09-06 МСК · ветка на момент правки: `feature/ad-sync`

---

## Стек и запуск

- Backend: FastAPI + SQLAlchemy 2.0 async + Pydantic 2. БД: Postgres 16 (asyncpg) /
  SQLite (aiosqlite) fallback. Схема — `Base.metadata.create_all` на старте (**нет Alembic**).
- Frontend: React 18 + Vite 6, nginx. Fetch-обёртка `/api` → backend.
- **FreeRADIUS 3.2 в backend-контейнере** (Debian bookworm) — панель пишет в реальный
  `/etc/freeradius/3.0`, валидирует `freeradius -XC`, перезагружает
  (`radius-reload.sh`). `entrypoint.sh` стартует FR (если конфиг валиден) + uvicorn.
- Деплой: `docker compose up -d --build` (db / backend :8000+1812/1813udp / frontend :8080).

## Backend `backend/app/`

| Файл | Роль |
|------|------|
| `main.py` | FastAPI app, lifespan → `init_models()` + `_group_sync_loop` (планировщик синка), IntegrityError→409, CORS, include роутеров, `/api/health` |
| `config.py` | `Settings` (env): `database_url`, `proxy_conf_path`, `clients_conf_path`, `ldap_conf_path`, `ldap_ca_path`, `radius_check_cmd`, `radius_reload_cmd`, `cors_origins`. В compose пути = реальный `/etc/freeradius/3.0/*`, check=`freeradius -XC`, reload=`radius-reload.sh`. `get_settings()` (lru_cache) |
| `Dockerfile` / `entrypoint.sh` / `radius-reload.sh` | backend-образ = panel + FreeRADIUS 3.2 (+ ldap/postgresql/utils). Панель управляет локальным FR |
| `database.py` | async engine, `SessionLocal`, `Base`, `get_db()`, `init_models()` (create_all) |
| `models.py` | ORM-таблицы + константы-enum |
| `schemas.py` | Pydantic in/out + валидаторы (зеркалят ограничения FR) |
| `crud.py` | тонкие операции на сущность + `log()` (audit) |
| `ldap_sync.py` | синк членов AD-групп через `ldap3` → `AdGroupMember`/`AdGroupSync` (ADR-0002) |
| `radius_config.py` | **весь FR-синтаксис**: рендереры + apply/validate/rollback |
| `routers/*.py` | HTTP-эндпоинты на сущность |

### Модель (`models.py`)

- `HomeServer` — upstream-таргет → `home_server{}`. Поля: name, type, ipaddr, port, secret,
  require_message_authenticator, status_check, response_window, zombie_period, revive_interval,
  check_interval, enabled, note. rel: `memberships`.
- `HomeServerPool` — `home_server_pool{}`. name, type, enabled, note. rel: `members` (ordered).
- `PoolMember` — упорядоченное членство (pool_id, home_server_id, position). uq(pool,hs).
- `Realm` — `realm{}`. name, auth_pool_id, acct_pool_id, nostrip, enabled, note **+ AD-гейт:**
  `ad_group_check`, `required_ad_group`, `username_normalization`, `ad_fail_mode`. rel: auth_pool/acct_pool.
- `Client` — NAS (от кого) → `client{}`. name, ipaddr(/CIDR), secret, shortname, nas_type,
  proto, require_message_authenticator, **preserve_source_ip** (custom client-поле для srcip-политики), enabled, note.
- `LdapSettings` — **singleton (id=1)** AD-подключение → `mods-enabled/ldap`. enabled, server,
  port, use_ldaps, start_tls, bind_dn, bind_password(секрет), base_dn, group_base_dn,
  group_filter, group_membership_attribute, cache_ttl, net_timeout, `group_sync_interval` **+ TLS:**
  `ca_cert`(PEM), `tls_require_cert`, `tls_min_version`.
- `AdGroupSync` — на группу (group_dn uniq): status(never/ok/error), member_count, error, last_synced_at.
- `AdGroupMember` — (group_dn, username uniq) — локальный список членов; читает FR sql-гейт.
- `AuditLog` — actor, action, entity, entity_ref, detail, created_at.

**Константы:** `HOME_SERVER_TYPES`, `POOL_TYPES`, `STATUS_CHECK_TYPES`, `USERNAME_NORMALIZATIONS`,
`AD_FAIL_MODES`, `NAS_TYPES`, `CLIENT_PROTOS`, `MESSAGE_AUTH_MODES`, `TLS_REQUIRE_CERT`.

### Рендереры + apply (`radius_config.py`)

- `render_home_server`, `render_pool`, `render_realm` → `render_proxy_conf(db)` (proxy.conf).
- `render_client` → `render_clients_conf(db)` (clients.conf; `preserve_source_ip = yes` custom-поле).
- `render_policy_conf(db)` → `policy.d/radiuspanel`: `radiuspanel_srcip` (inject NAS-IP по `%{client:preserve_source_ip}`, pre-proxy) + `radiuspanel_adgate` (per-realm: нормализация username + injection-guard + `%{sql:}` проверка членства в `ad_group_member` + статус `ad_group_sync` + fail_mode). Вызовы в site — вручную один раз (ADR-0002 A).
- `render_sql_module()` → `mods-enabled/sql` (rlm_sql_postgresql → Postgres панели; только для adgate `%{sql:}`).
- `render_ldap_module(cfg, *, mask_password=False)` → mods-enabled/ldap (+ `tls{}` с ca_file/require_cert/min_version при use_ldaps|start_tls).
- `apply_config(db)` → **multi-file**: [proxy.conf, clients.conf, policy.d/radiuspanel] + при
  `LdapSettings.enabled` ещё CA-файл (`ldap_ca_path`) и ldap-модуль (`ldap_conf_path`). `_write_with_backup` каждый,
  `radius_check_cmd` валидирует, `_rollback` всех при провале, затем `radius_reload_cmd`.
  Возвращает `ApplyResult(written_paths, validated, ...)`.
- `ConfigValidationError(output)`. Хелперы: `_quote`, `_quote_secret`, `_Backup`.
- `_run(cmd)` = `asyncio.to_thread(subprocess.run)` — **не** `create_subprocess_exec`
  (под uvloop конфликтует с двойным форком демона FreeRADIUS → apply висел).

### API-эндпоинты

- `/api/clients` GET/POST/PUT{id}/DELETE{id} (`routers/clients.py`)
- `/api/home-servers` GET/POST/PUT/DELETE (`routers/home_servers.py`)
- `/api/pools` GET/POST/PUT/DELETE (`routers/pools.py`)
- `/api/realms` GET/POST/PUT/DELETE — `_serialize` через `model_validate` + имена пулов (`routers/realms.py`)
- `/api/ldap` GET/PUT + `/preview.conf` (маска пароля) + `/ca.pem` (CA) + `/sync` GET(статус)/POST(синк сейчас) (`routers/ldap.py`)
- `/api/config/preview`, `/preview.conf`, `/clients-preview.conf`, `/policy-preview.conf`, `/apply` (POST), `/audit` (`routers/config.py`)
- `/api/health` (`main.py`)

## Frontend `frontend/src/`

| Файл | Роль |
|------|------|
| `main.jsx` | монтаж React |
| `App.jsx` | shell: sidebar (бренд-лого `/logo.png`), nav TABS, toast, counts. Рендер страниц по `tab` |
| `api.js` | `api.{clients,homeServers,pools,realms,ldap,config}` + `request()` |
| `components.jsx` | `Modal`, `Field`, `Spinner`, `Empty`, `StatusDot` |
| `pages/Clients.jsx` | CRUD клиентов (NAS) |
| `pages/HomeServers.jsx` | CRUD home servers |
| `pages/Pools.jsx` | CRUD пулов + порядок членов |
| `pages/Realms.jsx` | CRUD реалмов + поля AD-гейта (условно по чекбоксу) |
| `pages/LdapSettings.jsx` | форма AD/LDAP + превью модуля |
| `pages/ConfigPreview.jsx` | превью proxy.conf + apply (показывает `written_paths`) |
| `styles.css` | дизайн Interros (navy+gold), классы ниже |

**TABS:** clients → home-servers → pools → realms → ldap → config.

**CSS-словарь:** `.shell/.sidebar/.brand/.brand-mark/.nav`, `.page-head`, `.btn(.primary/.ghost/.danger/.sm)`,
`.table-wrap/table/.tag(.ok/.off/.accent)/.dot-status`, `.overlay/.modal/.field(.hint)/.grid-2/.check/.modal-actions`,
`.config-pane/pre.conf/.result/.empty/.toast/.spinner`.

## Файлы FR, которыми владеет панель (ADR-0001)

`proxy.conf` ✓ · `clients.conf` ✓ · `mods-enabled/ldap` ✓ (+ CA-файл, при enabled) ·
`policy.d/radiuspanel` ✓ (srcip + adgate per-realm sql-гейт) · `mods-enabled/sql` ✓ (при gated-realm).
Вызовы policy в site — вручную один раз. Apply/валидация — на всём наборе.

## Паттерн добавления сущности

model (+константы) → schema (Base/Create/Update/Out + валидаторы) → crud (list/get/create/update/delete + log)
→ router → `main.py` include → `radius_config.py` рендер (+ в `apply_config` targets) →
frontend: `api.js` + `pages/X.jsx` + `App.jsx` (TAB + counts).
