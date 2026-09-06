# ADR — реестр архитектурных решений

Что решили, почему, что отвергли. Даты — МСК. Формат: короткий Nygard-ADR.

| № | Дата (МСК) | Решение | Статус |
|---|-----------|---------|--------|
| [0001](0001-proxy-policy-scope-ad-gate-logs.md) | 2026-09-06 | Панель генерит policy/ldap/логи; AD-гейт per realm; логи в Postgres; fail-open | Accepted |
| [0002](0002-policy-gate-local-group-sync.md) | 2026-09-06 | Co-located FreeRADIUS; policy.d+include; синк AD-групп локально; source-IP per-client | Accepted |
