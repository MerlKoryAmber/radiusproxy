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
