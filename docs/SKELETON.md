# SKELETON — карта проекта

Актуальная структурная карта, чтобы **сверяться, а не перечитывать весь код**.
Обновлять **перед каждым push** (см. §22 CLAUDE.md). Читать после handoff и перед
началом задачи. Если что-то тут расходится с кодом — код прав, а скелет чинить.

**Обновлено:** 2026-09-11 МСК · ветка на момент правки: `fix/radius-site-wiring`

---

## Стек и запуск

- Backend: FastAPI + SQLAlchemy 2.0 async + Pydantic 2. БД: Postgres 16 (asyncpg) /
  SQLite (aiosqlite) fallback. Схема — `Base.metadata.create_all` на старте (**нет Alembic**).
- Frontend: React 18 + Vite 6, nginx. Fetch-обёртка `/api` → backend.
- **FreeRADIUS 3.2 в backend-контейнере** (Debian bookworm) — панель пишет в реальный
  `/etc/freeradius/3.0`, валидирует `freeradius -XC`, перезагружает
  (`radius-reload.sh`). `entrypoint.sh` стартует FR (если конфиг валиден) + uvicorn.
  **Site вшит в образ** (`backend/freeradius/site-default` → `sites-enabled/default`):
  зовёт `radiuspanel_route` (authorize) / `srcip` (pre-proxy) / `log` (post-auth+REJECT).
  Stub `policy.d/radiuspanel` вшит для `-XC` на первом старте. `/etc/freeradius/3.0` —
  **в образе, не volume** → панель **применяет конфиг на старте** (`_apply_on_boot`,
  самовосстановление после ребилда). ADR-0008.
- **HTTPS:** backend генерит self-signed cert в БД+том `panelcerts`; frontend nginx `443 ssl`
  + `80→443`, авто-reload по inotify при смене cert. Наружу **80/443** (не 8080).
- Деплой: `docker compose up -d --build` (db / backend :8000+1812/1813udp / frontend :80+:443).
  Все сервисы `restart: unless-stopped` — встают сами после ребута хоста.
  Все сервисы с пустым `http(s)_proxy`/`no_proxy=*` (не ходят во внешний прокси).
- **Хостовое CLI `rpp`** (`scripts/rpp.sh` + `scripts/lib/common.sh` → `/usr/bin/rpp`):
  меню/подкоманды update·uninstall·secrets·password·git-token·status·start/stop/restart
  (systemd unit `radiusproxy.service`)·logs·backup/restore (`storage/backup/`)·url. ADR-паттерн
  `docs/patterns/cli-menu-linux.md`. Секреты `.env` (`APP_ENCRYPTION_KEY`/`JWT_SECRET`, compose из env).

## Backend `backend/app/`

| Файл | Роль |
|------|------|
| `main.py` | FastAPI app, lifespan → `init_models()` + `_group_sync_loop` (планировщик синка), IntegrityError→409, CORS, include роутеров, `/api/health` |
| `config.py` | `Settings` (env): `database_url`, `proxy_conf_path`, `clients_conf_path`, `ldap_conf_path`, `ldap_ca_path`, `radius_check_cmd`, `radius_reload_cmd`, `cors_origins`. В compose пути = реальный `/etc/freeradius/3.0/*`, check=`freeradius -XC`, reload=`radius-reload.sh`. `get_settings()` (lru_cache) |
| `Dockerfile` / `entrypoint.sh` / `radius-reload.sh` | backend-образ = panel + FreeRADIUS 3.2 (+ ldap/postgresql/utils). Панель управляет локальным FR |
| `database.py` | async engine, `SessionLocal`, `Base`, `get_db()`, `init_models()` (create_all) |
| `models.py` | ORM-таблицы + константы-enum + `EncryptedStr` (TypeDecorator, шифрует секреты в БД) |
| `schemas.py` | Pydantic in/out + валидаторы (зеркалят ограничения FR) |
| `crud.py` | тонкие операции на сущность + `log()` (audit) |
| `ldap_sync.py` | `ldap3`: каталог всех групп (cn+dn → `AdGroupCatalog`) + членство групп из правил по DN (`AdGroupMember`/`AdGroupSync`) |
| `auth.py` | авторизация панели (stdlib): pbkdf2-хэш, hmac-токен, `ensure_seed` (admin/admin), `require_user` (гейт при `AuthSettings.enabled`) |
| `crypto.py` | Fernet шифрование секретов at-rest (ключ из `APP_ENCRYPTION_KEY`); `encrypt/decrypt`, формат `enc:<token>` (ADR-0005) |
| `tls.py` | self-signed генерация + валидация cert/key + `host_addresses()` (ADR-0006) |
| `radius_config.py` | **весь FR-синтаксис**: рендереры + apply/validate/rollback |
| `portable.py` | импорт/экспорт портируемого JSON (ссылки по имени): `export_bundle` + `plan_and_apply` (dry-run/apply, ADR-0007) |
| `routers/*.py` | HTTP-эндпоинты на сущность |

### Модель (`models.py`)

- `TargetServer` — upstream (куда) → `home_server{}` (FR-синтаксис). Поля: name, type, ipaddr,
  port, **secret (EncryptedStr)**, require_message_authenticator, status_check, response_window, zombie_period,
  revive_interval, check_interval, enabled, note. rel: `memberships`.
- `HomeServerPool` — `home_server_pool{}`. name, type, enabled, note. rel: `members` (ordered).
- `PoolMember` — упорядоченное членство (pool_id, **target_server_id**, position). uq(pool,ts).
- `Client` — NAS (от кого) → `client{}`. name, ipaddr(/CIDR), **secret (EncryptedStr)**, shortname,
  nas_type, proto, require_message_authenticator, **preserve_source_ip**, enabled, note. (routing/AD-гейт
  переехали на Rule — ADR-0004).
- `Rule` — **ordered** маршрут (ADR-0004, first-match). position, name, client_id,
  **match_username** (wildcard, ""=any), target_pool_id, ad_group_check, required_ad_group(cn),
  required_ad_group_dn, username_normalization, ad_fail_mode, enabled. rel: client, target_pool.
- `AdGroupCatalog` — (dn uniq, cn) каталог групп AD для автокомплита.
- (Realm-сущность удалён — realm генерится per-pool.)
- `LdapSettings` — **singleton (id=1)** AD-подключение → `mods-enabled/ldap`. enabled, server,
  port, use_ldaps, start_tls, bind_dn, bind_password(секрет), base_dn, group_base_dn,
  group_filter, group_membership_attribute, cache_ttl, net_timeout, `group_sync_interval` **+ TLS:**
  `ca_cert`(PEM), `tls_require_cert`, `tls_min_version`.
- `AdGroupSync` — на группу (group_dn uniq): status(never/ok/error), member_count, error, last_synced_at.
- `AdGroupMember` — (group_dn, username uniq) — локальный список членов; читает FR sql-гейт.
- `ProxyDecision` — лог решений RADIUS (пишет FR через `radiuspanel_log`/sql): created_at,
  nas_ip, packet_src_ip, username, realm, ad_result, reply, home_server.
- `AuthSettings` — singleton: `enabled` (флаг логина) + `ip_allowlist` (IP/CIDR-ограничение доступа).
- `TlsSettings` — singleton: `cert_pem`, `key_pem`(EncryptedStr), `is_self_signed` (HTTPS панели).
- `User` — админ панели (username, password_hash pbkdf2); seed `admin/admin`.
- `AuditLog` — actor, action, entity, entity_ref, detail, created_at.

**Константы:** `TARGET_SERVER_TYPES`, `POOL_TYPES`, `STATUS_CHECK_TYPES`, `USERNAME_NORMALIZATIONS`,
`AD_FAIL_MODES`, `NAS_TYPES`, `CLIENT_PROTOS`, `MESSAGE_AUTH_MODES`, `TLS_REQUIRE_CERT`.

### Рендереры + apply (`radius_config.py`)

- `render_home_server(TargetServer)`, `render_pool`, `render_realm_for_pool(name)` (realm=pool, nostrip) → `render_proxy_conf(db)` (proxy.conf; realm per pool, маршрут по клиенту).
- `render_client` → `render_clients_conf(db)` (clients.conf; `preserve_source_ip = yes` custom-поле).
- `render_policy_conf(db)` → `policy.d/radiuspanel`: `radiuspanel_route` — **ordered if/elsif по Rule** (матч `&Client-Shortname`[+`&User-Name =~ /wildcard/i`] → Proxy-To-Realm=пул + встроенный AD-гейт по DN + `&Tmp-String-1`; else reject) + `radiuspanel_srcip` + `radiuspanel_log`. Хелперы `_render_rule`, `_render_gate_body`, `_wildcard_to_regex`. Вызовы в site: authorize→route, pre-proxy→srcip, post-auth→log.
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

- `/api/clients` GET/POST/PUT{id}/DELETE{id} — secret write-only (`has_secret`) (`routers/clients.py`)
- `/api/target-servers` GET/POST/PUT/DELETE — secret write-only (`has_secret`, пустой=не менять) (`routers/targets.py`)
- `/api/pools` GET/POST/PUT/DELETE — members по target_server (`routers/pools.py`)
- `/api/rules` GET/POST/PUT/DELETE + POST `/reorder` (ids по порядку) (`routers/rules.py`)
- `/api/ldap` GET/PUT + `/preview.conf` + `/ca.pem` + `/test` POST (connect+bind проба, `ldap_sync.test_connection`) + `/sync` GET/POST (POST отдаёт сводку каталог/группы) + `/groups?q=` (автокомплит из каталога) (`routers/ldap.py`)
- `/api/config/preview`, `/preview.conf`, `/clients-preview.conf`, `/policy-preview.conf`, `/apply` (POST), `/audit`, `/export` GET, `/import` POST (`?dry_run=`) (`routers/config.py`)
- `/api/decisions` GET (лог решений, фильтры username/realm) (`routers/decisions.py`)
- `/api/logs/radius` GET (`?lines=&q=` — хвост `radius.log` FreeRADIUS: unknown client/bad secret; read-only) (`routers/logs.py`)
- `/api/auth/status|login|settings|password` (`routers/auth.py`) — **открыт**; остальные data/config-роутеры под `Depends(require_user)` (гейт при auth on)
- `/api/dashboard` GET — сводка (`routers/dashboard.py`)
- `/api/system/access` GET/PUT (ip_allowlist) · `/tls` GET/PUT + `/tls/self-signed` POST · `/host` GET (`routers/system.py`)
- `/api/health` (`main.py`). **Middleware:** IP-allowlist на `/api` (loopback всегда, пусто=все).


## Frontend `frontend/src/`

| Файл | Роль |
|------|------|
| `main.jsx` | монтаж React |
| `App.jsx` | shell: sidebar + **topbar** (`.topbar-title` + `UserMenu` справа), nav TABS, toast, counts. `authInfo` (user/enabled). Рендер страниц по `tab` |
| `api.js` | `api.{clients,homeServers,pools,realms,ldap,decisions,auth,config}` + `request()` (Bearer-токен, 401→login), `getToken/setToken` |
| `components.jsx` | `Modal`, `Field`, `Spinner`, `Empty`, `StatusDot`, `UserMenu` (топбар-дропдаун), `ChangePasswordModal` (new+confirm) |
| `pages/Clients.jsx` | CRUD клиентов (NAS) — только NAS + preserve_source_ip |
| `pages/TargetServers.jsx` | CRUD target servers |
| `pages/Pools.jsx` | CRUD пулов + порядок членов (target servers) |
| `pages/Rules.jsx` | ordered rules (up/down reorder) + модалка (client/username/pool/AD-гейт), `GroupPicker` автокомплит групп |
| `pages/LdapSettings.jsx` | форма AD/LDAP + превью + синк (`embedded` внутри Settings) |
| `pages/ConfigPreview.jsx` | превью proxy.conf + apply (показывает `written_paths`) |
| `pages/Portable.jsx` | Import/Export: экспорт JSON (download) + импорт файла → dry-run план → применить (ADR-0007) |
| `pages/Decisions.jsx` | лог решений RADIUS (фильтр по user) |
| `pages/Dashboard.jsx` | сводка (счётчики, статусы FR/AD/apply/security, последние решения) |
| `pages/Settings.jsx` | под-вкладки **Access** (login + IP-allowlist), **AD/LDAP**, **TLS** (замена cert), **Host** (read-only IP). Пароль — в топбар-меню |
| `pages/Login.jsx` | экран входа (показывается при auth on и 401) |
| `styles.css` | дизайн Interros (navy+gold), классы ниже |

**TABS:** **dashboard** → clients → targets → pools → rules → decisions → config → **portable** (Import/Export) → settings (Access/AD-LDAP/TLS/Host под-вкладки). Маршрут: ordered Rules (ADR-0004). HTTPS + IP-allowlist + no-proxy (ADR-0006). Импорт/экспорт JSON (ADR-0007).

## Скрипты деплоя (`scripts/`)

- `install.sh` — ставит docker+compose (при отсутствии) + git, клонит репо в `INSTALL_DIR`
  (деф. `/opt/radiusproxy`), собирает и поднимает стек, ждёт health. Самодостаточный (`curl|bash`).
  `.env`: `HOST_ADDRESSES` (IP хоста) + `HOST_HOSTNAME` (`hostname -f`) — контейнер их сам не видит; используются в Settings→Host и SAN сертификата (`tls.py`).
- `update.sh` — `git pull` + `compose up -d --build` (`--no-pull` = без pull); обновляет `rpp`+unit.
- `uninstall.sh` — `compose down -v --rmi local` (`--keep-data`, `--purge`); снимает `rpp`+unit.
- `rpp.sh` + `lib/common.sh` — хостовое CLI-меню (`/usr/bin/rpp`): все операции + backup/restore/password/secrets. Паттерн `docs/patterns/cli-menu-linux.md`.
- `lib/docker-proxy.sh` (`apply_docker_proxy`) — прокси для pull/build на хостах без прямого `docker.io`: резолвит прокси из env/`/etc/environment`, пишет systemd drop-in для dockerd (чинит pull) + экспортит `HTTP(S)_PROXY`/`NO_PROXY` для build. Зовётся из `install.sh`/`update.sh` до `compose up --build`; `docker-compose.yml build.args` пробрасывают в apt/npm. Runtime контейнеров не трогает. Knob: `DOCKER_HTTP_PROXY`, `DOCKER_PROXY_SKIP=1`.
**Auth-гейт (App.jsx):** на старте `api.auth.status()`; 401 → `<Login>`; иначе shell. Имя юзера в топбаре → дропдаун (Change password с подтверждением / Log out).

**CSS-словарь:** `.shell/.sidebar/.brand/.brand-mark/.nav`, `.page-head`, `.btn(.primary/.ghost/.danger/.sm)`,
`.table-wrap/table/.tag(.ok/.off/.accent)/.dot-status`, `.overlay/.modal/.field(.hint)/.grid-2/.check/.modal-actions`,
`.config-pane/pre.conf/.result/.empty/.toast/.spinner`, `.main-area/.topbar/.topbar-title/.content`,
`.user-menu(.-btn/.-dropdown/.-item)/.who`, `.settings-section/legend/.field-hint`, `.login-page/.login-box`.

## Файлы FR, которыми владеет панель (ADR-0001)

`proxy.conf` ✓ · `clients.conf` ✓ · `mods-enabled/ldap` ✓ (+ CA-файл, при enabled) ·
`policy.d/radiuspanel` ✓ (srcip + adgate per-realm sql-гейт) · `mods-enabled/sql` ✓ (при gated-realm).
Вызовы policy в site — вручную один раз. Apply/валидация — на всём наборе.

## Паттерн добавления сущности

model (+константы) → schema (Base/Create/Update/Out + валидаторы) → crud (list/get/create/update/delete + log)
→ router → `main.py` include → `radius_config.py` рендер (+ в `apply_config` targets) →
frontend: `api.js` + `pages/X.jsx` + `App.jsx` (TAB + counts).
