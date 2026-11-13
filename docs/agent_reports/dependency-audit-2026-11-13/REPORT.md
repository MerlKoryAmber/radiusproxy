# Аудит зависимостей — 2026-11-13 МСК

Источники: PyPI / npm registry (последние версии), OSV.dev (уязвимости **наших**
версий, включая транзитивные — резолв `pip install --dry-run --report` по
`backend/requirements.txt`), endoflife.date (сроки поддержки рантаймов).
Сырые выводы — ниже по разделам. Живой прод/лабу не смотрел (SSH с этой машины нет).

## Итог по приоритетам

| # | Что | Сейчас | Проблема | Касается нас? | Цель |
|---|-----|--------|----------|---------------|------|
| 1 | **starlette** (через fastapi) | 0.41.3 (fastapi 0.115.6 держит `<0.42`) | 7 уязвимостей, 3 HIGH | **Да: GHSA-86qp** — `request.url.path` подделывается через `Host`; наш IP-allowlist (`main.py:165`) решает по нему → обход. Порт 8000 опубликован наружу мимо nginx. Логин по умолчанию OFF | немедленно: `request.scope["path"]` в middleware; затем fastapi 0.162 (starlette 1.x) |
| 2 | **nginx** (образ фронта, смотрит в интернет) | `nginx:1.27-alpine` | ветка 1.27 **EOL 2025-06-24** (16 мес. без фиксов) | Да — рантайм на 80/443 | `nginx:1.30-alpine` (stable) |
| 3 | **cryptography** | 44.0.0 | 4 HIGH (в т.ч. уязвимый OpenSSL в wheel), фикс в 46–50 | Частично: бандл-OpenSSL — да; PKCS7/цепочки/SECT — не используем | 50.0.2 |
| 4 | **node** (стадия сборки фронта) | `node:20-alpine` | Node 20 **EOL 2026-04-30** | Слабо — только сборка, в рантайм не попадает | `node:22-alpine` / `24` LTS |
| 5 | **python base / FreeRADIUS** | `python:3.12-slim` (плавающий тег) | Python 3.12 — ок до 2028-10. Но тег переехал bookworm → trixie: версия FreeRADIUS из apt зависит от **даты сборки** (3.2.1 vs 3.2.7) — недетерминизм | Да — разные FR на разных средах | закрепить `python:3.12-slim-trixie`; проверить `freeradius -v` на HNPS-03 |
| 6 | **vite** | 6.4.3 | 5 уязвимостей (HIGH/MOD) — dev-server / launch-editor | Нет — в проде только `vite build`, dev-server не развёрнут | патч 6.4.4 попутно |

Без известных уязвимостей, просто отстали (обновлять пакетом вместе с #1 —
новый fastapi всё равно потянет свежий pydantic): fastapi 0.115.6→0.162.5,
uvicorn 0.34.0→0.54.0, sqlalchemy 2.0.36→2.1.8, pydantic 2.10.4→2.14.3,
pydantic-settings 2.7.0→2.16.2, aiosqlite 0.20.0→0.22.1, asyncpg 0.30.0→0.32.0.

**Не трогать сейчас:** React 18→19, Vite 6→8, plugin-react 4→6 — мажоры без
уязвимостей, отдельный проект. postgres 16 — поддержка до 2028-11; мажор = dump/restore.

**Замечание:** `ldap3 2.9.1` — последняя версия, но библиотека не развивается
с 2021. Риска сейчас не видно; держать в уме.

## Попутно найдено

- Порт backend `8000:8000` опубликован на все интерфейсы — API без TLS мимо
  nginx. install.sh/`update.sh` ходят в него с localhost (`/api/health`).
  Кандидат: `127.0.0.1:8000:8000`.
- `@fontsource/inter` нет в `package-lock.json` (доставляется `npm install` в сборке).
- `postgres:16-alpine`: `compose up --build` не перекачивает уже скачанный
  образ БД → минорные фиксы Postgres не приезжают без `docker compose pull`.

## Риски обновления

- starlette 0.x → 1.x — мажор; тестов/гейта нет (хвост handoff) → проверять на
  лабе сценарием §4 (UI + `-XC` + apply + Decisions).
- cryptography: используем Fernet + x509 builder/load (`tls.py`, ADR-0005) —
  API стабилен, но прогнать генерацию self-signed и расшифровку секретов.

## Сырые данные

### PyPI (ours → latest)
fastapi 0.115.6→0.162.5 · uvicorn 0.34.0→0.54.0 · sqlalchemy 2.0.36→2.1.8 ·
pydantic 2.10.4→2.14.3 · pydantic-settings 2.7.0→2.16.2 · aiosqlite 0.20.0→0.22.1 ·
asyncpg 0.30.0→0.32.0 · ldap3 2.9.1→2.9.1 · cryptography 44.0.0→50.0.2 ·
starlette 0.41.3→1.10.0

### npm (lock → latest)
react 18.3.1→19.3.1 · react-dom 18.3.1→19.3.1 · vite 6.4.3→8.3.8 ·
@vitejs/plugin-react 4.7.0→6.3.0 · @fontsource/inter 5.1.1→5.3.0 ·
esbuild 0.25.12→0.28.2 · rollup 4.63.1→4.68.3

### OSV — наши версии
- starlette 0.41.3: GHSA-2c2j-9gv5-cj73 [MOD] fix 0.47.2 multipart DoS ·
  GHSA-7f5h-v6xp-fcq8 [HIGH] fix 0.49.1 Range DoS (FileResponse) ·
  GHSA-82w8-qh3p-5jfq [HIGH] fix 1.3.1 form() limits ·
  GHSA-86qp-5c8j-p5mr [MOD] fix 1.0.1 **Host → request.url.path bypass** ·
  GHSA-jp82-jpqv-5vv3 [LOW] fix 1.3.0 · GHSA-wqp7-x3pw-xc5r [HIGH] fix 1.1.0
  StaticFiles UNC (Windows) · GHSA-x746-7m8f-x49c [MOD] fix 1.1.0 HTTPEndpoint
- cryptography 44.0.0: GHSA-537c-gmf6-5ccf [HIGH] fix 48.0.1 OpenSSL в wheel ·
  GHSA-g6cj-pr64-35w5 [HIGH] fix 50.0.0 PKCS7 Bleichenbacher ·
  GHSA-jwv3-5hgf-82ww [HIGH] fix 49.0.0 path-building DoS ·
  GHSA-r6ph-v2qm-q3c2 [HIGH] fix 46.0.5 SECT subgroup · GHSA-m959 [LOW] 46.0.6 ·
  GHSA-79v4 [LOW] 44.0.1
- vite 6.4.3: GHSA-587h [HIGH], GHSA-698v/r825/rq7h [MOD], GHSA-9jrq [LOW] — fix 6.4.4
- остальные прямые и транзитивные (anyio, h11 0.16.0, websockets, idna,
  pyasn1, …) — чисто.

### Использование Starlette (почему остальные CVE не наши)
`grep` по `backend/app`: нет FileResponse / StaticFiles / `request.form` /
HTTPEndpoint / UploadFile. Есть `request.url.path` в `main.py:165` (IP-allowlist).

### endoflife.date
python 3.12 eol 2028-10-31 · nodejs 20 eol **2026-04-30** (LTS живы: 22→2027-04,
24→2028-04, 26→2029-04) · nginx 1.27 eol **2025-06-24** (stable 1.30, mainline 1.31) ·
postgresql 16 eol 2028-11-09 (есть 17, 18) · debian 12 eol 2028-06, 13 eol 2030-06

---

## Результат применения (2026-11-13 МСК, ветка `fix/deps-2026-11`)

Коммиты: `04a3000` (порты через `.env`), `7b39c36` (security + deps).

Лаба 172.22.76.122 (CentOS Stream 9, стек на 18080/18443/18000/11812/11813), `update.sh`:

| Проверка | Результат |
|---|---|
| Версии в образе | Python 3.12.16, fastapi 0.162.5, starlette 1.10.0, uvicorn 0.54.0, SQLAlchemy 2.1.8, greenlet 3.5.6, pydantic 2.14.3, cryptography 50.0.2, asyncpg 0.32.0; Debian 13 trixie, FreeRADIUS 3.2.7; nginx 1.30.6 |
| `npm audit` (lock) | 0 уязвимостей (source-map-js 1.2.2, vite 6.4.6) |
| health / panel | `/api/health` 200, `https://:18443/` 200, ассеты 200, googleapis в index — 0 |
| `freeradius -XC` | Configuration appears to be OK |
| Рестарты контейнеров | 0 / 0 / 0 |
| Соседи (podman + docker) | 14 до = 14 после, имена совпадают |
| API smoke | dashboard, host, tls get, tls self-signed (серт на 18443 сменился), ldap test (структурный ответ), export, apply — 200; traceback в логе backend — 0 |
| Импорт NPS-бандла | dry-run create 15 / problems 0 → apply 15 → повторный dry-run update 15; apply validated; dashboard clients 4 / targets 2 / pools 2 / rules 7 |

Обход IP-allowlist (allowlist `10.99.99.0/24`, затем возвращён `""`):

| Запрос | До фикса | После |
|---|---|---|
| с Windows `:18000` (любой) | 200 с `X-Real-IP: 127.0.0.1` | порт закрыт (000) |
| nginx честно | 403 | 403 |
| nginx `X-Real-IP`/`X-Forwarded-For: 127.0.0.1` | 403 | 403 |
| `Host: x/api/health#` | 200 (на :18000) | 403 (loopback), 400 (nginx) |

Редирект 80→443 (`5b2b038`): `nginx.conf` — шаблон с `PANEL_HTTPS_PORT`; `http://…:18080/` → 301 `https://…:18443/` → 200, `nginx -t` OK, `$host` и пр. не тронуты.

Хвост: npm 11 `allowScripts` для esbuild (предупреждение, сборка ОК).

### UI-прогон в браузере (§4), 2026-11-13 МСК

Встроенный браузер, `https://172.22.76.122:18443` (self-signed серт лабы добавлен в доверенные Windows вручную владельцем).

- Все разделы открываются без ошибок, данные NPS-импорта видны: Clients 4, Target servers 2, Pools 2, Rules 7.
- Settings: все подвкладки (Access, AD/LDAP, RADIUS, Mail, TLS, Host) рендерятся. TLS показывает текущий self-signed. Host: `localhost` + IP хоста.
- AD/LDAP → «Test connection» даёт честный отказ «Server host / IP is empty».
- F5 оставляет на текущей вкладке (`radpanel_tab`).
- Config & apply: в `ConfirmDialog` нажато «Apply & reload» → «validated: true · reloaded: true», рестартов 0.
- Внешних запросов нет, шрифт Inter локальный (4 woff), ошибок в консоли нет.
- Не проверено руками: загрузка файлов (TLS PEM, импорт JSON через `FileButton`) — выбор файла встроенным браузером недоступен; API импорта проверен отдельно.
