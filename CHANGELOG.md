# CHANGELOG

Все смысловые изменения проекта. Даты — **МСК (UTC+3)**. Формат по духу
[Keep a Changelog](https://keepachangelog.com/ru/1.1.0/); версии — при появлении тегов.

## [Unreleased]

### 2026-09-10 МСК (3)

- **fix(ui):** загрузка файлов — стилизованная кнопка (`FileButton`) вместо
  нативного «Choose File». Применено в **Import / Export** (выбор JSON) и
  **Settings → TLS**: сертификат и ключ теперь грузятся **файлами** (.pem/.crt/.key),
  а не вставкой PEM-текста в textarea.
- **chore:** `.gitignore` — импорт/экспорт-бандлы (`*nps-import*.json`,
  `radiusproxy-config-*.json`) не кладём в гит (содержат реальные секреты).

### 2026-09-10 МСК (2)

- **feat(ADR-0007):** импорт/экспорт конфигурации портируемым JSON (раздел
  **Import / Export**). Экспорт `GET /api/config/export` (targets/pools/clients/rules,
  ссылки по имени, **без секретов**). Импорт `POST /api/config/import` с **dry-run**
  (план create/update + проблемы, ничего не пишет) → **применить** (одна транзакция,
  матч по имени). Секрет нужен только при создании нового target/client. Цель —
  миграция из Windows NPS (`netsh nps export ... exportPSK=YES` + скрины).
  Новый `backend/app/portable.py`, схемы Import*, страница `Portable.jsx`. Без сброса БД.

### 2026-09-10 МСК

- **fix(ops):** `restart: unless-stopped` на db/backend/frontend — после ребута
  хоста контейнеры поднимаются сами. Раньше при перезагрузке сервера панель
  оставалась лежать (Exited), пока не запустишь `docker compose up -d` вручную.

### 2026-09-07 МСК (3)

- **fix(ui):** контент панели тянется на всю ширину окна. `.content`/`.main`
  были капнуты `max-width:1180px` без центрирования → на широких мониторах
  прижимались влево при полноширинных topbar/sidebar. Теперь `flex:1`.

### 2026-09-07 МСК (2)

- **feat(ADR-0006):** **HTTPS** — self-signed cert из коробки (backend генерит в БД+том,
  nginx `443 ssl` + `80→443`, авто-reload по inotify). **Замена сертификата** в Settings→TLS
  (`/api/system/tls`, валидация, key шифруется). **Ограничение доступа по IP** (Settings→Access,
  `ip_allowlist`, middleware на `/api`, loopback всегда). **Host read-only** (Settings→Host).
  **Контейнеры без host-прокси** (`no_proxy=*`). **Dashboard** — сводка (`/api/dashboard`).
  Порты наружу 80/443 (не 8080). install.sh: `.env HOST_ADDRESSES`, https-health, firewall 80/443.

### 2026-09-07 МСК

- **feat(ops):** скрипты `scripts/install.sh` / `update.sh` / `uninstall.sh`. install
  ставит docker+compose+git при отсутствии, клонит репо, собирает и поднимает панель
  (+ FreeRADIUS + Postgres), ждёт health; update = pull+rebuild; uninstall = down -v (--keep-data/--purge).
- **feat(frontend):** AD/LDAP перенесён в **Settings** (под-вкладки Access + AD/LDAP);
  отдельный пункт nav убран.
- **feat(ADR-0004):** раздел **Rules** — упорядоченные правила маршрутизации (first-match):
  клиент [+ username wildcard] → target-пул + AD-гейт. `radiuspanel_route` = if/elsif цепочка.
  Routing/AD-гейт убраны с Client (Client = только NAS). AD-группа по **имени (cn)** с
  автокомплитом из засинканного **каталога групп** (`/api/ldap/groups`); членство матчится по DN.
  Reorder (`/api/rules/reorder`), синк каталога всех групп + членства по правилам.
- **security(ADR-0005):** секреты в БД теперь **шифруются** (Fernet, `APP_ENCRYPTION_KEY`)
  через `EncryptedStr` (target/client secret, bind_password). Секреты **write-only** в API
  (`has_secret`, пустое при update = не менять) — больше не возвращаются в GET. `cryptography` в deps.

### 2026-09-06 МСК

- **docs:** добавлен `CLAUDE.md` — метод работы с ИИ-агентом (взят из `MerlKoryAmber/2fa`,
  проектная секция переписана под FreeRADIUS Proxy Panel).
- **docs:** заведены `CHANGELOG.md` и `docs/handoff/CURRENT.md` (требование §6/§10 CLAUDE.md).
- **chore:** проект залит в репозиторий `github.com/MerlKoryAmber/radiusproxy` (ветка `main`).
- Начальный каркас MVP: FastAPI backend (редактор `proxy.conf`), React+Vite frontend,
  Docker Compose (Postgres 16 / backend / nginx).
- **feat(frontend):** дизайн Interros из соседнего 2fa — CSS-рескин `styles.css`
  (navy `#0f1b2e` + gold `#c9a96e`, Inter, UPPERCASE-заголовки таблиц, gold focus).
  Ветка `feature/interros-skin`. `docs/design/DESIGN.md` — токены + карта компонентов.
- **chore(deploy):** развёрнуто на тестовом CentOS Stream 9 (`192.168.0.178`) через
  docker-ce 29.8.0 + compose; панель на :8080, backend :8000, db healthy. Рескин
  проверен в браузере (§4). Соседний проект 2fa с сервера снесён (переехал).
- **feat:** AD-гейт кусок 1 — `LdapSettings` (AD-подключение) + поля realm
  (группа, нормализация, fail-mode), рендер `mods-enabled/ldap`, `/api/ldap`,
  UI AD/LDAP + поля в модалке realm. Пароль bind write-only. ADR-0001.
- **feat(frontend):** бренд-иконка из 2fa (лого в сайдбар + фавиконки).
- **feat:** раздел **Clients** — `clients.conf` (от кого принимаем: UAG/VPN/WiFi).
  Модель `Client`, рендер `client{}`, `/api/clients`, страница Clients. Apply
  обобщён на несколько файлов (proxy.conf + clients.conf) с бэкапом/rollback всех.
- **docs:** `docs/SKELETON.md` — карта проекта + правило §22 (сверяться, не перечитывать).
- **feat:** LDAPS TLS — загрузка CA-серта (PEM) + `require_cert`/`tls_min_version`,
  рендер `tls{}`, `apply_config` пишет ldap-модуль + CA при включённом AD, `/api/ldap/ca.pem`.
- **refactor:** `routers/realms.py` `_serialize` через `model_validate` — новые поля realm
  больше не требуют ручной правки сериализатора.
- **feat(infra):** FreeRADIUS 3.2 в backend-контейнере (шаг 0 к policy-гейту) — панель
  пишет в реальный `/etc/freeradius/3.0`, `freeradius -XC` валидирует, `radius-reload.sh`
  перезагружает. compose: пути на raddb, порты 1812/1813 udp. Панель+FR на одном хосте.
  `_run` через `asyncio.to_thread` (uvloop-фикс — apply висел). apply ~1с.
- **feat:** 4a — сохранение source-IP per-client (`preserve_source_ip` на Client) +
  `policy.d/radiuspanel` (`radiuspanel_srcip` рабочий, `radiuspanel_adgate` stub→4b).
  apply пишет policy.d; `/api/config/policy-preview.conf`; чекбокс в UI Clients.
- **feat:** 4b — синк AD-групп в панель + локальный sql-гейт. `ldap3`-синк
  (`ldap_sync.py`) членов групп → `AdGroupMember`/`AdGroupSync`; планировщик в lifespan
  (интервал `group_sync_interval`); `/api/ldap/sync` GET/POST; экран синка в UI.
  `render_sql_module` (rlm_sql→Postgres панели), `radiuspanel_adgate` per-realm:
  нормализация + injection-guard + `%{sql:}` членство + статус + fail_mode. IntegrityError→409.
- **feat:** 5 — лог решений RADIUS. `ProxyDecision` + политика `radiuspanel_log`
  (sql INSERT, guard User-Name), sql-модуль пишется всегда, `/api/decisions`, экран Decision log.
- **feat:** 6 — авторизация панели (флаг off по умолчанию). `AuthSettings`+`User` (seed admin/admin),
  `auth.py` (pbkdf2 + hmac-токен, stdlib), `/api/auth/*`, гейт роутеров `require_user`,
  экран Login + Access (тумблер/смена пароля/logout), Bearer-токен в `api.js`.
- **feat(frontend):** топбар с именем пользователя + дропдаун (UserMenu); смена пароля через
  всплывающую модалку с подтверждением (new+confirm). Настройки панели вынесены в раздел
  **Settings** (Access переименован); shell перестроен на `.main-area/.topbar/.content`.
- **refactor(ADR-0003):** маршрутизация **по клиенту**, не по realm. `Home server → Target server`
  везде (`/api/target-servers`). `Client` += target_pool + AD-гейт (переехал с realm).
  Realm-сущность/раздел удалены; realm генерится per-pool; `radiuspanel_route` ставит
  Proxy-To-Realm по `%{client:target_pool}`; `radiuspanel_adgate` теперь per-client.
  Fix: legend в Settings (наезд), сброс БД (переименование таблиц).
