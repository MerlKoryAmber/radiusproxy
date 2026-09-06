# Design notes — source IP, AD-group gating, logs (ЧЕРНОВИК, на обсуждение)

Статус: **на подумать**, не принято. Три требования владельца к проксированию.
Ключевой вывод: **всё это вне `proxy.conf`** — нужна policy виртуального сервера
(`unlang`), модуль `ldap` (AD) и модуль логов. Панель расширяется с «редактора
proxy.conf» до «proxy.conf + генератор policy + ldap + логи». Рендер FR-синтаксиса
остаётся в одном модуле (`backend/app/radius_config.py`) — добавляются рендереры.

---

## 1. Сохранить IP инициатора для проксированного запроса

**Реалия FR 3.2.** При проксировании FreeRADIUS пере-отправляет RADIUS-атрибуты
на home server, поэтому идентичность NAS **обычно уже едет** в пакете:

- `NAS-IP-Address` (attr 4) / `NAS-IPv6-Address` — ставит сам NAS, форвардится как есть.
- `Calling-Station-Id` (MAC/IP абонента) — тоже форвардится.

Проблема возникает если: (а) NAS не проставил `NAS-IP-Address`; (б) нужен **реальный
L3-источник** пакета (за NAT/цепочкой прокси) — он лежит в FR-внутреннем
`Packet-Src-IP-Address`, который на home server станет **IP прокси**, а не инициатора.

**Механизм:** секция `pre-proxy` в виртуальном сервере (НЕ proxy.conf):

```unlang
pre-proxy {
    # проставить NAS-IP-Address из реального источника, если пуст
    if (!&NAS-IP-Address) {
        update proxy-request { &NAS-IP-Address := "%{Packet-Src-IP-Address}" }
    }
    # опц.: донести истинный источник отдельным VSA / Operator-Name
    # update proxy-request { &Operator-Name := "src:%{Packet-Src-IP-Address}" }
}
```

**Панель:** тумблер на home_server или realm — «сохранять источник» (inject NAS-IP
из Packet-Src если пуст; опц. VSA с истинным источником). По умолчанию — форвард как есть.

**Развилка:** конкретный способ донесения (NAS-IP vs VSA vs Operator-Name) зависит от
того, что ждёт upstream. Уточнить у приёмной стороны.

---

## 2. Проверка присутствия пользователя в группе AD — для каждого рула отдельно

**Реалия.** Проверку делает **сам прокси** до проксирования (требование: гейт на
входящем запросе). Значит прокси ходит в AD по LDAP независимо от upstream-аутентификации.
Группа **разная на каждый realm/рул**.

**Нужно:**

1. Модуль `ldap` на AD: host, LDAPS (636), `base_dn`, bind DN + **пароль (секрет!)**,
   `groupname_attribute`, `membership_filter`, кэш группы (TTL — не долбить AD на каждый пакет).
2. Нормализация username под AD-идентити **per realm**: `user@realm` / `DOMAIN\user` /
   `sAMAccountName` — формат приходящего имени зависит от реалма, надо приводить к тому,
   что ищем в AD.
3. Policy-гейт (в `authorize`/`pre-proxy`), маппинг realm → требуемая группа:

```unlang
# псевдо, генерится панелью из data-модели realm↔group
if (&Realm == "corp.example.com") {
    if (!(&LDAP-Group == "CN=vpn-users,OU=Groups,DC=corp,DC=example,DC=com")) {
        reject          # нет в группе — не проксируем
    }
}
```

**Fail-mode:** решено **fail-open** (ADR-0001) — AD недоступен → проксировать без проверки.
Против §4, принято владельцем с митигациями: кэш last-known-good членства (TTL), громкий
аудит `ad_check = SKIPPED_AD_DOWN`, `fail_mode` параметром per realm (на чувствительных
рулах можно fail-closed).

**Data-модель:** realm/рул += `required_ad_group(s)`, `username_normalization`,
`fail_closed`. Глобально: одно AD-подключение (или несколько), секрет bind_pw — только
env/секреты, шифровать, не в логи.

**Замечание:** проверка группы = LDAP-поиск по имени, **не зависит** от метода аутентификации
(PAP/CHAP/MS-CHAP) — их делает upstream. Прокси только гейтит по членству.

---

## 3. Логи

**Что логировать на решение:** ts, NAS-IP (инициатор), Packet-Src-IP, User-Name
(сырой + нормализованный), matched realm/рул, проверенная AD-группа + результат
(pass/fail/AD-down), цель прокси (pool/home_server), ответ upstream (Accept/Reject/timeout),
латентность. **Пароли/секреты — никогда.**

**Куда (развилка):**

- **Postgres панели** (рекомендую): у панели уже есть БД. Модуль `sql` FreeRADIUS
  пишет решения в таблицу `proxy_audit`, UI панели показывает/фильтрует. Один источник
  правды, запросы, без шиппера.
- Файлы: `linelog` (структурная строка на событие) или `detail` (полный дамп пакета) —
  проще в FR, но для UI нужен парсер/шиппер.

Рекомендация: `sql`/`linelog` → Postgres, таблица аудита, экран в панели.
Ретеншн/ротация — параметром.

---

## Порядок обработки (сводно)

1. Приём → зафиксировать NAS-IP / Packet-Src.
2. Определить realm из User-Name (`suffix` + proxy.conf realm).
3. Нормализовать username под realm.
4. AD-гейт: членство в группе этого рула (fail-open + кэш + аудит, ADR-0001).
5. Pass → `pre-proxy`: сохранить/инжектить источник, `Proxy-To-Realm`.
6. Прокси на home_server_pool.
7. `post-proxy`: зафиксировать ответ upstream.
8. Лог решения в Postgres.

## Влияние на архитектуру

Панель генерирует не только `proxy.conf`, но и: `mods-enabled/ldap`, policy-сниппеты
в `sites-enabled` (`authorize`/`pre-proxy`/`post-proxy`), `mods-enabled/sql|linelog`.
Всё через `radius_config.py` (принцип «FR-синтаксис в одном модуле» сохраняется).
Секрет bind AD — шифрование + env. Нужен ADR: `docs/adr/` (пока нет).
```
