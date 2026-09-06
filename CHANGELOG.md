# CHANGELOG

Все смысловые изменения проекта. Даты — **МСК (UTC+3)**. Формат по духу
[Keep a Changelog](https://keepachangelog.com/ru/1.1.0/); версии — при появлении тегов.

## [Unreleased]

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
