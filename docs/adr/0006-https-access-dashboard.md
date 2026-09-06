# ADR-0006 — HTTPS, замена сертификата, IP-ограничение, no-proxy, Dashboard

- **Дата:** 2026-09-07 МСК
- **Статус:** Accepted

## Решения

1. **HTTPS (self-signed из коробки).** Backend при старте генерит self-signed cert
   в БД (`TlsSettings`, key зашифрован `EncryptedStr`) и материализует в общий том
   `panelcerts`. Frontend nginx: `443 ssl` + `80→443` redirect. Наружу порты 80/443.
   Смена cert без рестарта: `entrypoint.sh` фронта по `inotifywait` делает `nginx -s reload`.
2. **Замена сертификата в Settings→TLS.** `PUT /api/system/tls` (cert+key PEM) —
   валидация (`cryptography`), запись в БД + том → nginx reload. `POST /tls/self-signed`
   регенерит. Ключ шифруется, не отдаётся.
3. **IP-ограничение доступа (Settings→Access).** `AuthSettings.ip_allowlist`
   (IP/CIDR, по строкам). Middleware в `main.py` проверяет `X-Real-IP` на `/api`;
   не в списке → 403. **Loopback всегда разрешён**, пустой список = всем (анти-локаут).
4. **Контейнеры без host-прокси.** Во всех сервисах compose `http(s)_proxy=""`,
   `no_proxy=*` — трафик не уходит во внешний прокси.
5. **Смена IP хоста — только показ** (Settings→Host, read-only). Реальная смена =
   OS-level, из панели на том же хосте опасна (самоблокировка). IP хоста прокидывается
   через `.env HOST_ADDRESSES` (install.sh: `hostname -I`).
6. **Dashboard** — сводка: счётчики (clients/targets/pools/rules), статус FreeRADIUS,
   последний apply, AD-синк (каталог/члены/ok-error/last), безопасность (login/IP/TLS),
   последние решения. `GET /api/dashboard`.

## Последствия

- Доступ теперь `https://<host>` (self-signed → предупреждение браузера, пока не заменить).
- Новые таблицы `TlsSettings` + колонка `AuthSettings.ip_allowlist` → сброс тест-БД.
- Frontend-образ: +inotify-tools/openssl, entrypoint-watcher. Том `panelcerts` (backend rw, frontend rw).
- CORS_ORIGINS → `https://localhost` (dev). Порт 8080 больше не публикуется.
