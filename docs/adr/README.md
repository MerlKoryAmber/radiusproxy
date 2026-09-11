# ADR — реестр архитектурных решений

Что решили, почему, что отвергли. Даты — МСК. Формат: короткий Nygard-ADR.

| № | Дата (МСК) | Решение | Статус |
|---|-----------|---------|--------|
| [0001](0001-proxy-policy-scope-ad-gate-logs.md) | 2026-09-06 | Панель генерит policy/ldap/логи; AD-гейт per realm; логи в Postgres; fail-open | Accepted |
| [0002](0002-policy-gate-local-group-sync.md) | 2026-09-06 | Co-located FreeRADIUS; policy.d+include; синк AD-групп локально; source-IP per-client | Accepted |
| [0003](0003-routing-by-client.md) | 2026-09-06 | Маршрут по клиенту (не realm); Home→Target server; AD-гейт на клиенте; realm авто per-pool | Accepted |
| [0004](0004-rules-based-routing.md) | 2026-09-07 | Ordered Rules (client[+username wildcard]→pool+AD-гейт); AD-группа по cn; каталог+автокомплит | Accepted |
| [0005](0005-secrets-at-rest.md) | 2026-09-07 | Шифрование секретов at-rest (Fernet, APP_ENCRYPTION_KEY); секреты write-only в API | Accepted |
| [0006](0006-https-access-dashboard.md) | 2026-09-07 | HTTPS self-signed + замена cert; IP-ограничение; no-proxy; host read-only; Dashboard | Accepted |
| [0007](0007-portable-config-import-export.md) | 2026-09-10 | Портируемый JSON импорт/экспорт (миграция NPS); dry-run→apply; ссылки по имени | Accepted |
| [0008](0008-site-wiring-and-boot-apply.md) | 2026-09-11 | Вшитый прокси-site (зовёт политики) + stub + home_server default + автоприменение на старте | Accepted |
