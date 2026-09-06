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

## Хвосты (открыто)

- Нет `README.md#security` разбора для прод-выкатки (панель пишет `proxy.conf` и дёргает
  `RADIUS_RELOAD_CMD` — привилегированная операция, нужен threat-model перед прод).
- Нет тестов (`backend`/`frontend`), нет гейта `make verify` — §4 верификация вручную.
- Нет `docs/adr/` — реестр архитектурных решений (§10) при первом крупном решении.
- Дефолтные креды в `docker-compose.yml` (`radpanel/radpanel`) — только для локали, не прод.

## Не делать

- Не класть в git секреты / `.env` / реальные shared secret / IP боевых RADIUS-хостов.
- Не пушить код в `main` без команды человека (§6); docs — можно сразу.
- Не менять контракт `radius_config.py` рендера без сверки с моделью/API.

## Старт следующего агента

1. Прочитать `CLAUDE.md` (правила выше дефолта) и `README.md`.
2. `git fetch` + сверка `origin/main` (§8 — предполагать параллельные сессии).
3. Локальный запуск: `docker-compose up` → backend :8000, frontend :8080, db :5432.
4. Крупная задача — по пайплайну §2: АУДИТ → ПЛАН → РЕАЛИЗАЦИЯ → ВЕРИФИКАЦИЯ → ПРИЁМКА.
