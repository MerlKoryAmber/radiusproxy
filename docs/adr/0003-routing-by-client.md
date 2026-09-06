# ADR-0003 — Маршрутизация по клиенту (не по realm), rename Home→Target, AD-гейт на клиенте

- **Дата:** 2026-09-06 МСК
- **Статус:** Accepted (пересматривает маршрутную часть ADR-0001/0002)

## Контекст

Владелец уточнил модель: **проксирование выбирается по клиенту-источнику, а не по
`User-Name`/realm**. Имя пользователя к маршрутизации отношения не имеет — оно нужно
только для проверки вхождения в AD-группу перед пересылкой на таргеты.

## Решения

1. **Маршрут: Client → target-пул.** У `Client` поле `target_pool_id`. Панель в
   `authorize` ставит `&control:Proxy-To-Realm` из клиента (`radiuspanel_route`,
   читает `%{client:target_pool}`). `User-Name` в маршруте не участвует.
2. **Realm — плюмбинг.** Таблица `Realm` и раздел UI **удалены**. В `proxy.conf`
   генерится по одному `realm` на пул (имя = имя пула, `nostrip`), только чтобы
   FreeRADIUS мог проксировать в пул. Суффикс-матчинг не используется.
3. **AD-гейт — на клиенте.** Поля `ad_group_check`/`required_ad_group`/
   `username_normalization`/`ad_fail_mode` переехали с `Realm` на `Client`.
   `radiuspanel_adgate` рендерит блок per-client (ключ — `&Client-Shortname`).
   Синк групп собирает DN из клиентов.
4. **Rename Home server → Target server** везде (модель `TargetServer`, таблица
   `target_servers`, API `/api/target-servers`, UI). В `proxy.conf` синтаксис
   остаётся `home_server {}` (это FreeRADIUS).

## Последствия

- Схема БД изменилась (переименование таблиц, перенос колонок) → на тесте сброс БД
  (Alembic по-прежнему нет).
- `PoolMember.home_server_id` → `target_server_id`.
- Decision-log поле realm пишет `%{control:Proxy-To-Realm}` (целевой пул).
- Include в site: `authorize { radiuspanel_route radiuspanel_adgate }`,
  `pre-proxy { radiuspanel_srcip }`, `post-auth { radiuspanel_log }`.
- «Куда» задаётся на клиенте; пул выбирает стратегию (fail-over/load-balance).
