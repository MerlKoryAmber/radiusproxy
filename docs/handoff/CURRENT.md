# Handoff — CURRENT

Живой срез для следующего агента/сессии. Держать актуальным перед каждым смысловым
push (§6/§10 CLAUDE.md). Время — **МСК (UTC+3)**.

**Обновлено:** 2026-09-07 МСК

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
   - **4a:** source-IP per-client + policy.d-скаффолд + одноразовый include (готово, `feature/policy-srcip`)
   - **4b:** синк AD-групп (ldap3 + планировщик + таблицы) + sql-гейт (готово, `feature/ad-sync`);
     **хвост:** реальный синк членов не проверен (на 192.168.0.178 нет AD) — тест на AD-хосте.
5. Аудит-логи решений в Postgres (`sql`) + экран (готово, `feature/logs-auth`);
   **хвост:** реальная запись строк требует RADIUS-трафика (radclient/NAS) — не проверено без него.
6. Экран авторизации панели (флаг off) — готово, `feature/logs-auth`. seed admin/admin,
   pbkdf2+hmac-токен. **Прод:** сменить пароль + JWT_SECRET (env) до включения.
7. **Маршрут по клиенту (ADR-0003)** — готово, `feature/routing-by-client`: Home→Target server,
   Client→target_pool + AD-гейт на клиенте, Realm удалён (генерится per-pool), топбар/юзер-меню.
   Хвост: реальный AD/трафик по-прежнему не проверены (нет AD/NAS).
8. **Install/update/uninstall + AD/LDAP в Settings** — `feature/install-scripts`.
   `scripts/*.sh`; AD/LDAP под-вкладка Settings. Деплой-каталог по умолчанию `/opt/radiusproxy`.
9. **Rules (ADR-0004)** — `feature/rules`: ordered маршрутизация (client[+username wildcard]→pool+AD-гейт,
   first-match), routing/AD убраны с Client, AD-группа по cn + автокомплит из каталога, reorder.
   Хвост: реальный AD/трафик не проверены (нет AD/NAS) — каталог/членство/гейт тестируются на AD-хосте.
10. **Секреты at-rest (ADR-0005)** — Fernet/`APP_ENCRYPTION_KEY`, write-only API.
11. **HTTPS/access/dashboard (ADR-0006)** — **в main** (мерж `feature/https-access`,
    развёрнуто+проверено на 192.168.0.178 через curl): self-signed HTTPS (80/443),
    замена cert (Settings→TLS, live nginx-reload по inotify), IP-ограничение (Settings→Access,
    реальный IP клиента через `X-Real-IP`), **анти-локаут** (PUT отклоняет список без своего IP →400,
    мусор →422), no-proxy (`no_proxy=*`), Host read-only, **Dashboard**.
    Доступ теперь `https://<host>` (self-signed). Порт 8080 не публикуется. `.env HOST_ADDRESSES`.
    **Восстановление при локауте:** `docker compose exec db psql -U radpanel -d radpanel -c "UPDATE auth_settings SET ip_allowlist=''"`.
    Прод: заменить cert; задать `APP_ENCRYPTION_KEY`/`JWT_SECRET`.

**Решения по куску 4 (2026-09-06):** вариант A (policy.d + include); source-IP per-client;
группы синкать раз ~30 мин в панель и сравнивать локально (не per-packet AD); FR ставится
контейнером вместе с панелью, панель им полностью управляет. → ADR-0002 (завести).

## Хвосты (открыто)

- Нет `README.md#security` разбора для прод-выкатки (привилегированная запись конфигов + reload).
- Нет тестов (`backend`/`frontend`), нет гейта `make verify` — §4 верификация вручную.
- **Нет Alembic:** схема через `create_all` — новые таблицы создаются, но новые колонки
  на существующих таблицах НЕ мигрируются (нужен drop БД или Alembic).
- ~~секреты в БД плейнтекстом~~ — **зашифрованы** (ADR-0005, Fernet/`APP_ENCRYPTION_KEY`),
  секреты write-only в API. Прод: задать `APP_ENCRYPTION_KEY`/`JWT_SECRET` в env (не дев-дефолт);
  ротация ключа = пере-шифрование (пока нет).
- Дефолтные креды в `docker-compose.yml` (`radpanel/radpanel`) — только для локали, не прод.
- **Reload FR = pkill+restart**, оставляет defunct-зомби (init:true убран — ломал apply).
  Косметика; при желании — proper reaper/HUP позже. Также `freeradius -HUP` не перечитывает proxy.conf.
- **Exec-бит `.sh` на Windows:** checkout сбрасывает 755→644; `git merge`/commit может
  занести не-exec скрипты. На Win-машине `git config core.filemode false`; после мержа
  проверять `git ls-files -s '*.sh'` и чинить `git update-index --chmod=+x` (см. `.gitattributes` eol=lf).

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
