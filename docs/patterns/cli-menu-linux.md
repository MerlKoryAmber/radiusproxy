# Pattern: Linux host CLI management menu

Перенесено из соседнего проекта (`MerlKoryAmber/2fa` → `docs/patterns/cli-menu-linux.md`)
и адаптировано под FreeRADIUS Proxy Panel. Переносимые требования к меню управления
продуктом на Linux-хосте. Не ADR продукта, не замена `install.sh`/`update.sh` — обёртка и UX.

**Реализация в этом репо:** `scripts/rpp.sh` (+ `scripts/lib/common.sh`) → `/usr/bin/rpp`
(`ensure_cli`/`ensure_unit` в `common.sh`; ставит install.sh, обновляет update.sh, снимает uninstall.sh).

---

## Зачем

Оператор на сервере: **одна команда** `rpp` → нумерованное меню (те же действия — подкомандами).

---

## Контракт (обязательно)

| Правило | Деталь |
|---------|--------|
| Entry | `/usr/bin/<name>` обязательно (`/usr/local/bin` — доп., но не вместо: `secure_path` root часто без него). |
| Обёртка | В `/usr/bin/<name>` тонкий wrapper; логика в дереве продукта (`scripts/rpp.sh`). Путь — `/etc/rpp/repo_root`. После `git pull` меню свежее. |
| Root | Только root / `sudo rpp`. |
| Без args | Интерактивное меню (цикл → действие → меню). |
| С args | Сразу действие; код выхода ≠ 0 при ошибке/отмене. |
| Опасное | Confirm `[y/N]`. Уничтожение данных (purge, restore поверх БД) — **два** confirm. |
| Не дублировать | `update`/`uninstall` зовут `scripts/update.sh`/`uninstall.sh`. |
| Cwd при update | `cd /tmp` перед update. |
| Язык меню | **English labels** (tty1 часто без кириллицы). |
| Цвета | Один accent (green) + plain; `NO_COLOR`/не-TTY → без ANSI. |
| Секции | Разделять линией `————————————————————————————————`. |
| Выравнивание | Номера вправо в поле ширины 2 (` 9.` / `10.`). |
| Секреты | PAT/пароли не в лог, не в argv, не в `git remote -v` для пользователя (URL без userinfo). |
| `/dev/tty` | Проверять доступность (`printf '' >/dev/tty`), иначе stdin — не ломаться в агентах/pipe. |

## Структура меню

```
  RADIUS PROXY PANEL  (/opt/radiusproxy)
————————————————————————————————
   0. Exit
————————————————————————————————
   1. Update (git pull + rebuild)
   2. Update without pull
   3. Uninstall (keep data)
   4. Uninstall + volumes (PURGE)
————————————————————————————————
   5. Set encryption / JWT secrets
   6. Reset admin password
   7. Set git token (private repo)
————————————————————————————————
   8. Status
   9. Start stack
  10. Stop stack
  11. Restart stack
  12. Logs
————————————————————————————————
  13. Backup DB + config
  14. Restore from backup
  15. Panel URL / health
————————————————————————————————
```

Порядок секций (lifecycle → credentials/git → runtime → data → info) сохранять.
Подкоманды-зеркало: `update update-nopull uninstall uninstall-purge secrets password
git-token status start stop restart logs backup restore url help`.
Prompt: `Please enter your selection [0-15]:`.

## Наши привязки (адаптация)

- **update/uninstall** → `scripts/update.sh [--no-pull]` / `scripts/uninstall.sh [--keep-data|--purge]`.
- **secrets** → `.env` `APP_ENCRYPTION_KEY`/`JWT_SECRET` (compose читает из env; дефолт при unset).
  Смена `APP_ENCRYPTION_KEY` ломает уже зашифрованные секреты → два confirm, только на пустой панели.
- **password** → сброс admin: пароль по stdin в backend-контейнер (`auth.hash_password`), не в argv. Мин. длина 4 (как API).
- **git-token** → URL из `origin`; PAT проверяется через `GET https://api.github.com/user` (не только `ls-remote`), при провале — откат origin.
- **runtime** → systemd unit `radiusproxy.service` (oneshot + RemainAfterExit + compose up/down); fallback на compose.
- **backup/restore** → `storage/backup/<stamp>/` (`pg_dump --clean --if-exists` + `.env`); restore = два confirm, `.env` отдельным confirm. `storage/` в `.gitignore`.
- **url/health** → `https://<host>` + локальный health curl.

## Чеклист переноса

1. `docs/patterns/cli-menu-linux.md` (этот файл).
2. `scripts/rpp.sh` + `scripts/lib/common.sh` (wrapper/unit — `ensure_*`/`remove_*`).
3. Вшить в install/update/uninstall.
4. systemd unit продукта.
5. English меню + секции + выравнивание.
6. Секреты — не в update-интерактиве.
7. git-token: URL из origin; PAT через API.
8. backup **и** restore; `.gitignore` на `storage/`.
9. Прогон на lab: меню, cancel опасного, backup↔restore, stop→start, плохой PAT.

## Не делать

- Кириллица в меню (tty1 — квадраты). Радуга ANSI. Спрашивать git URL, известный из origin.
- Менять IP NIC хоста из меню без узкого ТЗ. `git add .`; PAT в репо/world-readable.
