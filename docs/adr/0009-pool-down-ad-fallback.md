# ADR-0009 — Fallback на 1-й фактор (AD) при недоступности 2FA-пула

- **Дата:** 2026-09-12 МСК
- **Статус:** Accepted

## Контекст

За панелью — 2-факторная аутентификация (2FA-сервер = target-пул). Если пул
**полностью недоступен**, все входы отваливаются. Нужен опциональный аварийный
режим: проверить **1-й фактор** (пароль AD) локально и **впустить**, пропустив 2-й.
Компромисс доступность↔безопасность — осознанный обход 2FA на время аварии.

## Решение

- Флаг **`Rule.pool_down_fallback`** (по правилу, галка в UI + красное предупреждение).
- Механизм FreeRADIUS: у пула `home_server_pool { … fallback = radiuspanel-fallback }`.
  `fallback` срабатывает, только когда **все реальные члены мертвы**. Виртуальный
  home-server `radiuspanel-fallback { virtual_server = radiuspanel_fallback }` →
  локальный виртуальный сервер `radiuspanel_fallback`:
  1. **SQL-гейт**: пускает только если есть enabled-правило с `pool_down_fallback`
     для этого клиента (`c.shortname = %{Client-Shortname}`).
  2. `ldap` (authorize) ищет юзера по `(sAMAccountName=%{User-Name})`.
  3. `Auth-Type LDAP { ldap }` — **bind паролем** (PAP) в AD.
  4. Успех → Access-Accept; иначе Reject. Результат в Logs: `pool-down-1fa` /
     `pool-down-reject` / `pool-down-nouser` / `pool-down-blocked`.
- `render_ldap_module` получил `user { filter = "(sAMAccountName=%{User-Name})" }`
  — **двойные кавычки** обязательны (одинарные = литерал, `%{}` не раскрывается).
- Рендерится только когда AD включён **и** есть fallback-правило; иначе
  `sites-enabled/radiuspanel-fallback` удаляется (чтобы `-XC` был чист).
- Миграция: `ALTER TABLE rules ADD COLUMN IF NOT EXISTS pool_down_fallback` (`_migrate`).

## Требования / ограничения

- **PAP**: пароль AD должен приходить в `User-Password` (проверено с UAG=PAP). MS-CHAP
  потребовал бы ntlm_auth (не входит в объём).
- AD/LDAP должен быть **доступен**, когда пул лёг (иначе fallback не сработает).
- Это **обход 2FA** — только по явной галке; входы видны в Logs с меткой.

## Логирование

Fallback-vserver пишет свою строку в Decision log с меткой `pool-down-1fa` (accept) /
`pool-down-reject` / `pool-down-nouser` / `pool-down-blocked` — по ней виден обход 2FA.
Основной site при этом тоже пишет строку проксированного исхода (realm=пул, `pass`),
т.е. на fallback-вход приходится **две** записи. Дедуп через reply-атрибут не сделан:
`Class` от виртуального home-server не пропагируется в reply основного запроса
(проверено). Метка `pool-down-1fa` для аудита достаточна; чистый single-row — хвост.

## Проверка

Живой AD `merl.loc` (DC 192.168.0.175): пул с недоступным таргетом → `radclient`
с `merl/amber` → **Access-Accept** (bind `CN=merlkory,OU=Merl_Users,DC=Merl,DC=loc`);
неверный пароль → **Access-Reject**. `freeradius -XC` — OK.

Повторная live-верификация 2026-09-12 (после компакта) на 192.168.0.178:
decision-лог показал `merl/amber → pool-down-1fa → Access-Accept`, неверный пароль
→ `pool-down-reject → Access-Reject` (radius.log: `ldap: Bind credentials
incorrect`). Клиентский `radclient` из-за `revive_interval` даёт ложные коды на
первом пакете (праймит ещё живой таргет) — доверять только серверному decision-логу.

**Важно:** живой конфиг на сервере может быть устаревшим — флаг `pool_down_fallback`
на правиле не активирует fallback, пока конфиг не **переприменён** (apply). При
включении фичи на боевом обязательно нажать Config → apply.

**Смежная находка (вынесена в отдельный fix):** target-сервер типа не `auth+acct`
(`auth`/`acct`/`coa`) в проксирующем пуле роняет `-XC` (`Unknown home_server`);
тип ограничен единственным рабочим `auth+acct`.
