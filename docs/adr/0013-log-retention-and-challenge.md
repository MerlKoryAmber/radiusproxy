# ADR-0013 — Ретенция логов + логирование Access-Challenge

- **Дата:** 2026-09-22 МСК
- **Статус:** Accepted

## Контекст

Два пробела, оба всплыли при разборе UAG/2FA push→TOTP:

1. **Логи копятся без предела** — ни `proxy_decision` (БД), ни `radius.log`
   (диск) не чистились. На боевом трафике диск/БД однажды заполнятся.
2. **Проксируемый Access-Challenge не виден в Decisions.** Он приходит от 2FA
   (2FA просит OTP), панель его пробрасывает клиенту, но если клиент не отвечает
   (Horizon так и делает) — запрос по таймауту становится reject, и в лог
   попадает только reject. Challenge исчезает. (Проброс challenge самим проксом
   доказан на стенде отдельно — ADR-0011-контекст; проблема была в видимости.)

## Решение

### Ретенция proxy_decision (БД)
- Поле `RadiusSettings.decision_retention_days` (дней; **0 = хранить вечно**),
  дефолт **30**, настраивается в Settings → RADIUS. Миграция `_migrate`.
- Фоновый `_decision_cleanup_loop` (main.lifespan): раз в сутки `DELETE FROM
  proxy_decision WHERE created_at < now()-N days`. Ошибки не убивают loop.

### Ротация radius.log (диск)
- `logrotate` добавлен в образ; конфиг `freeradius/logrotate-radius`:
  **size 50M, rotate 5, compress, copytruncate** → потолок ~250 MB.
- `copytruncate` — ротация на месте, FreeRADIUS не нужно перезапускать/слать
  сигнал. В slim-образе нет cron → `entrypoint.sh` гоняет `logrotate` ежечасно
  фоновым циклом.

### Логирование Access-Challenge
- Логируется через **`Post-Auth-Type Challenge { radiuspanel_log }`** в post-auth
  — канонический хук FR 3.2 для проксируемого challenge. Проверено на боевом
  `freeradius -X` (HNPS-03): 2FA прислал `Access-Challenge`, строка записалась в
  proxy_decision (`u1807 | hmk2fa | Access-Challenge`), challenge ушёл клиенту.
- Попытка продублировать в **post-proxy** через `%{reply:Packet-Type}` НЕ
  работает: в post-proxy этот xlat даёт `0`, не `Access-Challenge`
  (`EXPAND %{reply:Packet-Type} --> 0` в `-X`). Ветка убрана как бесполезная —
  `Post-Auth-Type Challenge` покрывает всё.

### Установлено при разборе (важно, не баг)
- Наш прокси challenge пробрасывает клиенту **полно**: State + Reply-Message на
  месте. Разница длины (пришло 105 → ушло 100, −5 байт) = **снятый `Proxy-State`**
  (0x313438): прокси обязан убрать свой Proxy-State из ответа перед отправкой
  клиенту (RFC 2865). Клиенту он не нужен — это НЕ потеря нужного атрибута.
- Значит проблема «UAG/Horizon по push-таймауту не показывает TOTP» — **не в
  нашем проксе**: valid challenge доходит до клиента, но Horizon не отвечает 2-м
  запросом со State (Checkpoint отвечает). Сторона UAG/2FA.

## Проверка

- `py_compile` / `bash -n` — OK. `freeradius -XC` на сгенерированном — проверить
  на тесте.
- Ретенция proxy_decision: строка 40 дней удалена, свежая осталась (проверено
  на тесте). logrotate: `logrotate -f` реально ротирует radius.log (copytruncate).
- Challenge-лог: проверено **на боевом HNPS-03** `freeradius -X` — реальный
  Access-Challenge от 2FA записан в Decisions через `Post-Auth-Type Challenge`,
  challenge доставлен клиенту. post-proxy-ветка убрана (не срабатывала).
