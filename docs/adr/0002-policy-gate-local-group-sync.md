# ADR-0002 — Policy-гейт: co-located FreeRADIUS, локальный синк AD-групп, policy.d

- **Дата:** 2026-09-06 МСК
- **Статус:** Accepted
- **Контекст:** [ADR-0001](0001-proxy-policy-scope-ad-gate-logs.md), [NOTES](../design/NOTES_proxy_policy.md)

## Решения

1. **FreeRADIUS co-located с панелью, панель им полностью управляет.** FR 3.2 стоит
   в том же backend-контейнере (Debian bookworm). Панель пишет в реальный
   `/etc/freeradius/3.0`, валидирует `freeradius -XC`, перезагружает. На боевом хосте —
   тот же принцип: панель + FR на одной машине. (Отменяет «развязанность» из ранней формулировки.)

2. **Интеграция политики — вариант A: policy.d-сниппет + одноразовый include.**
   Панель генерит `policy.d/radiuspanel` (`radiuspanel_adgate`, `radiuspanel_srcip`)
   целиком; админ **один раз** вписывает вызовы в `authorize`/`pre-proxy` своего сайта.
   Панель НЕ владеет `sites-enabled/default` (там чужая auth-логика — eap/mschap/…).
   Отвергнуто: отдельный виртуальный сервер (дублирование listen); владеть default-сайтом (опасно).

3. **AD-группы: синк в панель + сравнение локально (не per-packet AD).** Планировщик
   (лёгкий asyncio-таск, без Celery) раз ~30 мин тянет членов требуемых групп через
   `ldap3` в таблицу панели (`AdGroupMember`: realm/группа → username + synced_at, статус).
   Гейт в FR сравнивает локально через `sql`-модуль (запрос к Postgres панели) — тот же
   `sql`, что для аудит-логов (кусок 5). Плюсы: AD-сбой не роняет гейт (список от последнего
   синка), быстрее, не долбит AD. Fail-mode применяется к свежести списка, не к живому AD.

4. **Source-IP — per-client тумблер.** Поле `preserve_source_ip` на `Client` (источник —
   свойство NAS). Рендер в `radiuspanel_srcip` (`pre-proxy`):
   `if (!&NAS-IP-Address) { update proxy-request { &NAS-IP-Address := "%{Packet-Src-IP-Address}" } }`.

## Порядок реализации

- **Шаг 0** (готово): FR 3.2 в контейнере + `-XC` валидация + reload.
- **4a:** `preserve_source_ip` на Client + генерация `policy.d/radiuspanel` (srcip + скелет adgate)
  + include-инструкция; apply пишет policy.d.
- **4b:** `ldap3` синк-подсистема + `AdGroupMember` + экран статуса синка + `sql`-модуль + adgate-запрос.

## Последствия

- Backend-образ крупнее (freeradius + ldap/postgresql/utils). Приемлемо.
- Новые зависимости: `ldap3` (синк), позже конфиг `sql`-модуля FR → Postgres панели.
- `sql`-модуль FR ходит в ту же БД, что панель, — общая сеть compose.
- Reload = рестарт демона (`radius-reload.sh`); HUP не перечитывает proxy.conf целиком.
