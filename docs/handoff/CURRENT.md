# Handoff — CURRENT

Живой срез для следующего агента/сессии. Держать актуальным перед каждым смысловым
push (§6/§10 CLAUDE.md). Время — **МСК (UTC+3)**.

**Обновлено:** 2026-09-06 МСК

---

## Срез проекта

FreeRADIUS Proxy Panel (`radiusproxy`) — веб-панель управления проксированием RADIUS
в FreeRADIUS 3.2.x. Редактор `proxy.conf` (home_server / home_server_pool / realm)
с превью, валидацией `freeradius -XC` и безопасным apply с откатом.

- **Стек:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async, Pydantic 2,
  Postgres 16 (asyncpg) / SQLite (aiosqlite) fallback; React 18 + Vite 6, nginx; Docker Compose.
- **Ключевой модуль:** вся FreeRADIUS-специфика рендера — только в
  `backend/app/radius_config.py`.
- **Данные:** панель держит свою БД (home_servers, pools, realms, audit log);
  FreeRADIUS для проксирования БД не нужен — конфиг рендерится в `proxy.conf`.
- **Статус:** MVP-каркас для расширения, **не** прод (см. `README.md#security`).

## Сделано

- Начальный каркас: backend `backend/app` (`main.py`, `models.py`, `schemas.py`,
  `crud.py`, `database.py`, `config.py`, `radius_config.py`, `routers/`), frontend
  `frontend/src`, `docker-compose.yml`.
- Проект в git: `github.com/MerlKoryAmber/radiusproxy`, ветка `main`.
- `CLAUDE.md` — правила работы агента (адаптирован под этот проект).
- `CHANGELOG.md`, `docs/handoff/CURRENT.md` — заведены.
- **Дизайн Interros** (из соседнего 2fa) применён CSS-рескином `frontend/src/styles.css`
  + `docs/design/DESIGN.md`. Ветка `feature/interros-skin` (НЕ в main — ждёт merge по команде).
- **Развёрнуто на тесте:** CentOS Stream 9 `192.168.0.178`, docker-ce, `/root/radiusproxy`,
  `docker compose up -d --build`; панель :8080, backend :8000, db healthy. Проверено в браузере.
- **Дизайн Interros + бренд-иконка** — в main. **AD-гейт кусок 1** (LdapSettings + поля
  realm + рендер ldap + UI) — в main. **Clients** (`clients.conf`, раздел + рендер +
  multi-file apply) — ветка `feature/clients`.
- ADR-0001 расширен: скоуп файлов панели (clients.conf обяз., CA-серт для LDAPS,
  экран авторизации с флагом off, multi-file apply).

## План (куски, ADR-0001)

1. ~~AD data-модель + ldap рендер~~ (готово, main)
2. ~~Clients / clients.conf~~ (готово, main)
3. ~~AD/LDAP: CA-сертификат + require_cert (LDAPS)~~ + ldap в apply (готово, `feature/ldap-tls`)
4. Policy-гейт (обсуждён, ADR-0002):
   - **шаг 0:** FreeRADIUS 3.2 в backend-контейнере (готово+проверено, `feature/radius-stack`);
     apply валидирует+reload реальный FR за ~1с. `_run` через `asyncio.to_thread` (uvloop-фикс).
   - **4a:** source-IP per-client + policy.d-скаффолд + одноразовый include
   - **4b:** синк AD-групп в панель (планировщик + ldap3 + таблица) + sql-гейт (сравнение локально)
5. Аудит-логи решений в Postgres (`sql`) + экран
6. Экран авторизации панели (флаг, off на dev)

**Решения по куску 4 (2026-09-06):** вариант A (policy.d + include); source-IP per-client;
группы синкать раз ~30 мин в панель и сравнивать локально (не per-packet AD); FR ставится
контейнером вместе с панелью, панель им полностью управляет. → ADR-0002 (завести).

## Хвосты (открыто)

- Нет `README.md#security` разбора для прод-выкатки (привилегированная запись конфигов + reload).
- Нет тестов (`backend`/`frontend`), нет гейта `make verify` — §4 верификация вручную.
- **Нет Alembic:** схема через `create_all` — новые таблицы создаются, но новые колонки
  на существующих таблицах НЕ мигрируются (нужен drop БД или Alembic).
- `bind_password` (AD) в БД плейнтекстом — шифрование до прода (ADR-0001).
- Дефолтные креды в `docker-compose.yml` (`radpanel/radpanel`) — только для локали, не прод.
- **Reload FR = pkill+restart**, оставляет defunct-зомби (init:true убран — ломал apply).
  Косметика; при желании — proper reaper/HUP позже. Также `freeradius -HUP` не перечитывает proxy.conf.

## Деплой-сервер (тест)

- CentOS Stream 9 `192.168.0.178`, root по SSH-ключу `~/.ssh/radiusproxy_ed25519`.
- docker-ce 29.8.0 + compose; podman 5.8.5 тоже стоит (не используется). SELinux Enforcing.
- Каталог `/root/radiusproxy`, обновление: `git pull && docker compose up -d --build`.
- `/root/linotp-migrate` (46 МБ) чужие данные — не трогать без явного «да».

## Не делать

- Не класть в git секреты / `.env` / реальные shared secret / IP боевых RADIUS-хостов.
- Не пушить код в `main` без команды человека (§6); docs — можно сразу.
- Не менять контракт `radius_config.py` рендера без сверки с моделью/API.

## Старт следующего агента

1. Прочитать `CLAUDE.md` (правила выше дефолта) и `README.md`.
2. `git fetch` + сверка `origin/main` (§8 — предполагать параллельные сессии).
3. Локальный запуск: `docker-compose up` → backend :8000, frontend :8080, db :5432.
4. Крупная задача — по пайплайну §2: АУДИТ → ПЛАН → РЕАЛИЗАЦИЯ → ВЕРИФИКАЦИЯ → ПРИЁМКА.
