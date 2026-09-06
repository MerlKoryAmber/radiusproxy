# CHANGELOG

Все смысловые изменения проекта. Даты — **МСК (UTC+3)**. Формат по духу
[Keep a Changelog](https://keepachangelog.com/ru/1.1.0/); версии — при появлении тегов.

## [Unreleased]

### 2026-09-06 МСК

- **docs:** добавлен `CLAUDE.md` — метод работы с ИИ-агентом (взят из `MerlKoryAmber/2fa`,
  проектная секция переписана под FreeRADIUS Proxy Panel).
- **docs:** заведены `CHANGELOG.md` и `docs/handoff/CURRENT.md` (требование §6/§10 CLAUDE.md).
- **chore:** проект залит в репозиторий `github.com/MerlKoryAmber/radiusproxy` (ветка `main`).
- Начальный каркас MVP: FastAPI backend (редактор `proxy.conf`), React+Vite frontend,
  Docker Compose (Postgres 16 / backend / nginx).
- **feat(frontend):** дизайн Interros из соседнего 2fa — CSS-рескин `styles.css`
  (navy `#0f1b2e` + gold `#c9a96e`, Inter, UPPERCASE-заголовки таблиц, gold focus).
  Ветка `feature/interros-skin`. `docs/design/DESIGN.md` — токены + карта компонентов.
- **chore(deploy):** развёрнуто на тестовом CentOS Stream 9 (`192.168.0.178`) через
  docker-ce 29.8.0 + compose; панель на :8080, backend :8000, db healthy. Рескин
  проверен в браузере (§4). Соседний проект 2fa с сервера снесён (переехал).
