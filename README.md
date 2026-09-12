# FreeRADIUS Proxy Panel

Веб-панель управления **проксированием RADIUS** в FreeRADIUS 3.2.x. Маршрутизация
настраивается не в конфиг-файлах руками, а через UI: клиенты (NAS), целевые
серверы, пулы и **правила** (client [+ маска username] → пул, опционально с
AD-гейтом). Панель рендерит из своей БД валидный конфиг FreeRADIUS, проверяет его
через `freeradius -XC` и применяет с автооткатом при ошибке.

Бэкенд — FastAPI, фронтенд — React (Vite), FreeRADIUS 3.2 живёт **внутри**
backend-контейнера. Разворачивается одной командой через Docker Compose.

> Каркас для расширения. Перед боевым использованием прочитай раздел
> [Безопасность](#безопасность).

## Идея

FreeRADIUS 3.2 конфигурируется **файлами, не SQL**. Панель держит **свою** БД
(клиенты, целевые серверы, пулы, правила, настройки AD/TLS/входа, логи) и
рендерит её в реальные файлы FreeRADIUS. Вся FreeRADIUS-специфика рендера — в
одном модуле `backend/app/radius_config.py`, поэтому рендерер можно менять, не
трогая API и модель данных.

Панель управляет этими файлами (пути Debian, `/etc/freeradius/3.0`):

| Файл | Что рендерится |
|------|----------------|
| `proxy.conf` | `home_server` (целевые серверы), `home_server_pool` (пулы + fallback), `realm` (по одному на пул) |
| `clients.conf` | клиенты (NAS): ip, secret, source-IP |
| `policy.d/radiuspanel` | политики маршрутизации/логирования/AD-гейта (зовутся из site) |
| `sites-enabled/default` | прокси-site, вызывающий политики панели |
| `sites-enabled/radiuspanel-fallback` | виртуальный сервер fallback на 1-й фактор AD (ADR-0009) |
| `mods-enabled/ldap`, `mods-enabled/sql` | AD/LDAP (когда включён) + SQL для AD-гейта и лога решений |

### Как ходит запрос

```
   NAS (клиент) ──Access-Request──► FreeRADIUS (backend-контейнер)
                                        │  читает конфиг, отрендеренный панелью
                                        ▼
                             правило: client[+username] → пул
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                                ▼
                  пул жив: проксирует           пул мёртв целиком +
                  на 2FA (LinOTP/…)             галка pool_down_fallback:
                                                проверка 1-го фактора (пароль AD, PAP)
```

Опционально перед проксированием — **AD-гейт**: членство пользователя в группе
AD (по каталогу, синхронизируемому панелью), fail-open / fail-closed на правиле.

## Версия FreeRADIUS

Целевая линия — **3.2.x** (проверено на 3.2.5 / 3.2.10), классическая модель
`proxy.conf`.

> **FreeRADIUS 4:** в v4 `proxy.conf` удалён (`realm` / `home_server` /
> `home_server_pool` больше нет, проксирование через `rlm_radius`). Панель на v4
> **не** нацелена; при миграции меняется только `radius_config.py`.

## Структура проекта

> **Актуальная карта — `docs/SKELETON.md`** (файлы/роли, модель, эндпоинты,
> рендереры). Живой срез и старт следующего агента — `docs/handoff/CURRENT.md`.
> Архитектурные решения — `docs/adr/` (реестр `docs/adr/README.md`). Этот README —
> обзор; при расхождении верить SKELETON/коду.

```
freeradius-panel/
├── docker-compose.yml         # db + backend (+FreeRADIUS 3.2) + frontend (nginx, HTTPS)
├── scripts/                   # install.sh / update.sh / uninstall.sh + rpp.sh (host CLI)
├── backend/app/
│   ├── radius_config.py       # ★ весь FreeRADIUS-синтаксис: рендер + validate/apply/rollback
│   ├── models.py              # TargetServer / Pool / Client / Rule / Ldap/Tls/Auth/Radius / Decision / Audit
│   ├── portable.py            # импорт/экспорт портируемого JSON (миграция из NPS, ADR-0007)
│   ├── tls.py crypto.py auth.py ldap_sync.py   # HTTPS-серт / шифрование секретов / вход / AD-синк
│   ├── schemas.py crud.py database.py config.py main.py routers/
│   └── requirements.txt
└── frontend/src/
    ├── pages/                 # Dashboard/Clients/TargetServers/Pools/Rules/Logs/Config/Portable/Settings/Help
    ├── api.js  App.jsx  components.jsx
```

## Запуск

### Вариант A — Docker (Postgres), FreeRADIUS внутри

FreeRADIUS 3.2 работает **внутри** backend-контейнера; панель пишет реальные
`/etc/freeradius/3.0`, проверяет `freeradius -XC` и перезагружает.

```bash
docker compose up -d --build
```

- UI панели: **<https://localhost>** (self-signed — браузер предупреждает; замени в Settings → TLS)
- API + Swagger: <http://localhost:8000/docs>
- RADIUS: `:1812/udp` (auth), `:1813/udp` (acct)
- Вход по умолчанию **выключен** (открыто); дефолтный админ `admin` / `admin`.

При старте панель **автоматически применяет** конфиг из БД (ADR-0008), так что
после пересборки контейнера (raddb в образе, не volume) маршрутизация
восстанавливается сама.

### Вариант A2 — установка на Linux-хост

```bash
curl -fsSL https://raw.githubusercontent.com/MerlKoryAmber/radiusproxy/main/scripts/install.sh | sudo bash
```

Ставит Docker + compose + git, клонирует в `/opt/radiusproxy`, поднимает стек и
ставит хостовое CLI **`rpp`** (`sudo rpp` → меню: update / status / logs / backup /
restore / password / secrets / …). Для боевого: задать стойкие секреты
`rpp secrets` и заменить сертификат в Settings → TLS.

**За прокси (нет прямого `docker.io`)?** Демон docker — systemd-сервис и не видит
прокси из шелла (`dial tcp registry-1.docker.io:443: i/o timeout`).
`install.sh`/`update.sh` подхватывают прокси из окружения или `/etc/environment`
и настраивают демон + сборки. Если `sudo` срезает окружение — передать явно:

```bash
curl -fsSL https://raw.githubusercontent.com/MerlKoryAmber/radiusproxy/main/scripts/install.sh \
  | sudo DOCKER_HTTP_PROXY=http://HOST:PORT bash
```

Работающие контейнеры остаются без прокси намеренно (ходят в LDAP/RADIUS
напрямую); прокси — только для pull/build. Отключить: `DOCKER_PROXY_SKIP=1`.

### Вариант B — локальная разработка (SQLite, без БД)

Бэкенд:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload            # http://localhost:8000
```

Фронтенд:

```bash
cd frontend
npm install
npm run dev                              # http://localhost:5173
```

Vite-dev проксирует `/api` на `http://localhost:8000`.

## Разделы UI

| Раздел | Что делает |
|--------|-----------|
| **Dashboard** | сводка: клиенты/таргеты/пулы/правила, статус FreeRADIUS, время последнего apply, TLS/вход/IP-ограничение, состояние AD-синка |
| **Clients** | клиенты (NAS): ip, shared secret (шифруется), source-IP, message-authenticator |
| **Target servers** | целевые RADIUS-серверы (`home_server`); тип фиксирован `auth+acct` (прочие роняют `-XC` в проксирующем пуле) |
| **Pools** | пулы (`home_server_pool`): стратегия (fail-over/…), упорядоченные члены |
| **Rules** | правила маршрутизации (сверху вниз, первое совпадение): client [+ маска username] → пул; опц. AD-гейт; опц. fallback на 1-й фактор AD при мёртвом пуле |
| **Logs** | вкладки «Decisions» (лог решений) и «Server log» (tail radius.log) |
| **Config & apply** | превью `proxy.conf` / `clients.conf` / `policy.d` + apply с подтверждением |
| **Import / Export** | портируемый JSON (миграция из Windows NPS): dry-run → применить |
| **Settings** | Access (вход + IP-ограничение), AD/LDAP (+тест, синк групп), RADIUS (`max_request_time`), TLS (замена/самоподпись серта), Host |
| **Инструкция** | руководство по панели на русском для неспециалистов |

## Валидация и apply

На apply панель бэкапит текущие файлы, пишет новые, запускает `freeradius -XC`
и **откатывает всё к бэкапу при провале валидации** — сломанный конфиг до
работающего сервера не доходит. Reload — только после успешной проверки.

В Docker-варианте пути и команды заданы в `docker-compose.yml`. Для запуска
панели рядом с внешним FreeRADIUS — в `backend/.env`:

```bash
PROXY_CONF_PATH=/etc/freeradius/3.0/proxy.conf   # Debian/Ubuntu
RADIUS_CHECK_CMD=freeradius -XC                   # dry-run перед apply
RADIUS_RELOAD_CMD=systemctl reload freeradius     # reload после успешного apply
```

Пути по дистрибутивам: Debian/Ubuntu `/etc/freeradius/3.0/`, RHEL/CentOS `/etc/raddb/`.

## API

Все эндпоинты под `/api`, интерактивные доки — `/docs`.

| Метод | Путь | Назначение |
|-------|------|-----------|
| GET/POST/PUT/DELETE | `/api/clients` | клиенты (NAS) |
| GET/POST/PUT/DELETE | `/api/target-servers` | целевые серверы (`home_server`) |
| GET/POST/PUT/DELETE | `/api/pools` | пулы + упорядоченные члены |
| GET/POST/PUT/DELETE, POST `/reorder` | `/api/rules` | правила маршрутизации |
| GET | `/api/config/preview` · `/preview.conf` · `/clients-preview.conf` · `/policy-preview.conf` | превью рендера |
| POST | `/api/config/apply` | запись + валидация + reload (422 при невалидном) |
| GET/POST | `/api/config/export` · `/import` | портируемый JSON (dry-run → apply) |
| GET | `/api/config/audit` | лог изменений/применений |
| GET | `/api/dashboard` | сводка для Dashboard |
| GET | `/api/decisions` · `/api/logs/radius` | лог решений · tail radius.log |
| GET/PUT, POST `/test` `/sync`, GET `/groups` | `/api/ldap` | настройки AD/LDAP, тест, синк групп, автокомплит |
| GET/PUT | `/api/system/access` · `/system/radius` · `/system/tls` (+`/self-signed`), GET `/system/host` | доступ / RADIUS-настройки / TLS / хост |
| GET/POST/PUT | `/api/auth/status` · `/login` · `/settings` · `/password` | вход (опциональный) |

## Безопасность

- **Секреты шифруются at-rest** (Fernet, ключ `APP_ENCRYPTION_KEY`). В боевом
  **обязательно** сменить дефолтный ключ (`rpp secrets`) — при смене ключа ранее
  зашифрованные секреты не расшифруются.
- **Вход** опциональный (Settings → Access); дефолтный админ `admin`/`admin` —
  сменить пароль (`rpp password` или в UI). Аудит-лог пишет `actor`.
- **HTTPS**: nginx только по 443 (80 → 301), self-signed из коробки — заменить
  сертификат в Settings → TLS.
- **IP-ограничение** доступа к панели (Settings → Access) с анти-локаут защитой.
- `JWT_SECRET` для сессий — сменить в боевом (`rpp secrets`).
- `.env`, ключи, дампы БД — не в git.

## Fallback на 1-й фактор AD (ADR-0009)

Если за панелью 2FA (target-пул = 2FA-сервер) и пул **полностью недоступен**, по
галке `pool_down_fallback` на правиле панель на время аварии проверяет только
**1-й фактор** — пароль в AD (bind, PAP) — и впускает. Это осознанный обход 2FA;
такие входы помечаются в Logs как `pool-down-1fa` (успех) / `pool-down-reject`
(неверный пароль). Требует включённого AD/LDAP и PAP от NAS. Подробности и
ограничения — `docs/adr/0009-pool-down-ad-fallback.md`.

## Дальнейшее

- Alembic-миграции (сейчас модель авто-создаётся, `_migrate()` в `database.py` для ALTER-ов)
- Живой статус целевых серверов через FreeRADIUS `status-server`
- Рендерер FreeRADIUS 4 за тем же API
