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

### Логирование Access-Challenge (несбиваемо)
- В `sites-enabled/default` **post-proxy**: `if ("%{reply:Packet-Type}" ==
  "Access-Challenge") { radiuspanel_log }` — пишет строку **сразу** при
  получении challenge от home, ДО того как запрос может переклассифицироваться
  в reject. Строковый xlat `%{reply:...}` (attr-compare `&reply:Packet-Type` в
  post-proxy FR 3.2 не матчит — проверено `freeradius -X`).
- `Post-Auth-Type Challenge { radiuspanel_log }` в post-auth оставлен (ловит
  challenge на путях, где до post-auth доходит). На боевом challenge-then-reject
  сработает post-proxy-ветка.

## Проверка

- `py_compile` / `bash -n` — OK. `freeradius -XC` на сгенерированном — проверить
  на тесте.
- Стенд с фейковым challenge-home: challenge → строка `Access-Challenge` в
  Decisions (проверено на прошлой итерации; post-proxy-ветку перепроверить).
- Ретенция: выставить малый срок, вставить старую строку, дождаться/дёрнуть
  cleanup → строка удаляется. logrotate: `logrotate -f` → radius.log ротируется.
- Live на реальном UAG/2FA (видимость challenge при таймаут-reject) — **TODO**
  (реальный 2FA недоступен из сессии; проверка на боевой HNPS-03).
