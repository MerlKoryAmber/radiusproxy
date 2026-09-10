# ADR-0007 — Портируемый импорт/экспорт конфигурации (миграция из NPS)

- **Дата:** 2026-09-10 МСК
- **Статус:** Accepted

## Контекст

Нужен перенос конфигурации из Windows NPS (RADIUS-прокси Microsoft), выполняющего
похожую функцию. У владельца — скрины NPS + машинный экспорт `netsh nps export
filename=nps.xml exportPSK=YES` (клиенты, remote RADIUS server groups, connection
request / network policies, PSK). Хочется загрузить файл настроек в панель.

## Решения

1. **Формат — свой JSON** (не парсер NPS XML). Чистый bundle 1:1 с моделью панели,
   сущности ссылаются по **имени** (не по id) → читаемо и переносимо между БД.
   Финальный файл собирается вручную из NPS-данных (агент маппит NPS → модель),
   панель его только валидирует и применяет. NPS XML-парсер не делаем — XML
   громоздкий/хрупкий, а разовую миграцию проще собрать в наш JSON.
2. **Импорт — dry-run → подтверждение.** `POST /api/config/import?dry_run=true`
   (дефолт) валидирует ссылки и возвращает план (create/update по каждой сущности +
   проблемы), ничего не пишет. `dry_run=false` применяет весь bundle одной
   транзакцией. Матч по **имени**: есть → update, нет → create. Правила с пустым
   именем всегда create (нечем матчить).
3. **Порядок применения** (разрешение ссылок): target servers → pools (+ члены по
   именам) → clients → rules (client/pool по именам; позиция новых — в хвост).
4. **Секреты.** Не экспортируются (write-only at-rest, ADR-0005). На импорте secret
   обязателен только при создании нового target/client; пустой = не менять
   существующий. PSK берутся из `netsh export ... exportPSK=YES`.
5. **AD-группы.** В bundle — по cn (как в Rules, ADR-0004). DN при импорте берётся
   из `required_ad_group_dn` если задан, иначе резолвится из синканного каталога
   (`AdGroupCatalog`) по cn (если однозначно); иначе пусто — досинкать AD и
   перевыбрать в UI.
6. **Экспорт** — `GET /api/config/export`: текущее состояние в тот же формат
   (бэкап/перенос). UI-раздел **Import / Export** (загрузка файла → dry-run → план →
   применить; кнопка экспорта). После импорта — **Config & apply** пишет в FreeRADIUS.

## Маппинг NPS → модель

| Windows NPS | Сущность панели |
|---|---|
| RADIUS Clients (friendly name, IP, shared secret) | `Client` (name, ipaddr, secret, shortname) |
| Remote RADIUS Server Groups → серверы | `TargetServer` (каждый) + `Pool` (группа) |
| Connection Request Policy (условие → форвард в группу) | `Rule` (client[+username] → target_pool) |
| Network Policy, условие *Windows-Groups* | `Rule.ad_group_check` + `required_ad_group` (cn) |
| Условия: Client Friendly Name / NAS IP / User Name | `Rule.client` + `match_username` (wildcard) |

## Последствия

- Новый модуль `backend/app/portable.py` (export_bundle + plan_and_apply), схемы
  Import* в `schemas.py`, эндпоинты `/api/config/export|import`, раздел UI Portable.
- **Без новых таблиц/колонок** — сброс БД не нужен.
- Экспортный файл секретов не содержит — для полного бэкапа PSK хранить отдельно.
- Импорт не пишет в FreeRADIUS сам — только в БД панели; выкат — через Config & apply.
