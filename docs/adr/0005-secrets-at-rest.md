# ADR-0005 — Шифрование секретов at-rest + write-only в API

- **Дата:** 2026-09-07 МСК
- **Статус:** Accepted

## Контекст

Shared-секреты (`TargetServer.secret`, `Client.secret`) и `LdapSettings.bind_password`
хранились в БД **плейнтекстом**; target/client `secret` ещё и **возвращался** в GET API.

## Решения

1. **Шифрование at-rest (обратимое).** Секреты нужны FR в открытом виде (рендер в
   конфиг), поэтому не хэш, а **Fernet** (AES-128-CBC+HMAC), ключ из
   `APP_ENCRYPTION_KEY` (env). Прозрачно через SQLAlchemy `EncryptedStr`
   (`TypeDecorator`): в Python — plaintext, в БД — `enc:<token>`. Значения без
   префикса `enc:` считаются legacy-plaintext (без миграции).
2. **Секреты write-only в API.** `TargetServerOut`/`ClientOut` больше не отдают
   `secret` — только `has_secret`. Create требует secret; Update с пустым = не менять
   (как `bind_password`/`has_password` у LDAP).
3. **Ключи.** `APP_ENCRYPTION_KEY`, `JWT_SECRET` — env; дев-дефолты «insecure»,
   в прод задать. Смена `APP_ENCRYPTION_KEY` делает старые секреты нечитаемыми.

## Последствия

- Зависимость `cryptography`. Тип колонок секретов → `EncryptedStr` (Text) → сброс тест-БД.
- `User.password` уже pbkdf2 (не трогаем). DB-креды в compose — инфра, отдельно.
- Хвост: ключ в env-файле на хосте — защищать правами; ротация ключа = re-encrypt (нет пока).
