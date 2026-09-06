# ADR-0004 — Ordered Rules routing, AD-группа по имени, каталог+автокомплит

- **Дата:** 2026-09-07 МСК
- **Статус:** Accepted (пересматривает routing из ADR-0003)

## Контекст

Маршрут-как-поле-на-Client (ADR-0003) заменяется **упорядоченным набором правил**.
Плюс: AD-группа задаётся по имени (cn), не по DN; при наборе — автокомплит из
засинканного каталога групп.

## Решения

1. **Раздел Rules — ordered, first-match-wins.** Таблица `Rule` (position). Матч:
   `client_id` (обяз.) **+ опц. `match_username`** (wildcard `*`). Action: `target_pool_id`
   + AD-гейт (group/normalization/fail-mode). enabled. Оценка сверху вниз; не совпало
   ни одно → **reject** (не проксируем).
2. **Routing/AD-гейт переезжают с Client на Rule.** Client = только NAS
   (ip/secret/shortname/nas_type/proto/msg-auth/preserve_source_ip). Поля
   ad_group_check/required_ad_group/username_normalization/ad_fail_mode/target_pool
   удалены с Client.
3. **FR-рендер:** `radiuspanel_route` (authorize) — цепочка `if/elsif` по правилам:
   матч `&Client-Shortname == "<sn>"` [+ `&User-Name =~ /<wildcard→regex>/`] → set
   `Proxy-To-Realm` (= пул) + inline AD-гейт + результат в `&Tmp-String-1`; иначе reject.
4. **AD-группа по имени (cn).** Автокомплит `/api/ldap/groups?q=` из каталога.
   Выбор возвращает {cn, dn}; храним `required_ad_group` (cn, показ) + `required_ad_group_dn`
   (для однозначности). Членство синкается и матчится по **DN** (надёжно), UI — по cn.
5. **Каталог групп.** Таблица `AdGroupCatalog(dn uniq, cn)`. Планировщик тянет все
   группы под `base_dn` (`(objectClass=group)`, атрибуты cn) — для автокомплита.
   Членство — только для групп, используемых правилами (по DN).

## Последствия

- Схема БД меняется (новые Rule/AdGroupCatalog, урезан Client) → сброс тест-БД.
- `radiuspanel_adgate` больше не per-client отдельно — гейт встроен в правило route.
- Синк AD: две задачи — каталог (все группы, без членов) + членство (группы из правил).
- Wildcard→regex: `*`→`.*`, экранирование прочего; якоря `^…$`, case-insensitive.
