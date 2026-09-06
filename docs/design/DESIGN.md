# FreeRADIUS Proxy Panel — Design System

Источник оформления: соседний проект **MK 2FA** → **Squid Proxy Manager**
(Interros corporate identity). Портирован в React-фронт radiusproxy как чистый
CSS-рескин (`frontend/src/styles.css`), без изменения разметки.

## Принципы

- Тёмный navy сайдбар (`#0f1b2e`) + тёмный контент, акцент gold `#c9a96e`.
- Активный пункт меню — gold левый бордюр (`border-left`), **без иконок**.
- Одна колонка форм; модалки для create/edit; `.grid-2` для парных полей.
- Заголовки таблиц — UPPERCASE, `letter-spacing`, приглушённый цвет.
- Технические значения (`ipaddr:port`, имена блоков, конфиг) — моноширинно (`.mono`).
- Focus — gold рамка + мягкое кольцо `rgba(201,169,110,0.25)`.

## Tokens (`frontend/src/styles.css` → `:root`)

```css
--ir-primary: #0f1b2e;   /* navy sidebar */
--ir-accent:  #c9a96e;   /* gold accent / primary btn */
--bg:         #0c121c;   /* content background */
--panel:      #141c2a;   /* surface */
--panel-2:    #1a2436;   /* raised surface / inputs */
--border:     #2a3548;
--text:       #e8ecf1;
--muted:      #8a94a3;
--ok:  #3daa6d;  --warn: #d4a017;  --danger: #e06b63;
--sans: "Inter", system-ui, …;   --mono: ui-monospace, …;
```

## Шрифт

**Inter** 400/500/600/700 — подключён Google Fonts в `frontend/index.html`
(в 2fa был локальный, чтобы без CDN; здесь CDN допустим). Системный фолбэк в `--sans`.

## Компоненты (классы → где)

| Класс | Что | Файл |
|-------|-----|------|
| `.shell` / `.sidebar` / `.nav button.active` | навигация, navy + gold accent | `App.jsx` |
| `.btn` `.primary` `.ghost` `.danger` `.sm` | кнопки; primary = gold на navy text | все |
| `.table-wrap` / `table` / `.tag` / `.dot-status` | таблицы данных, статусы | `pages/*.jsx` |
| `.overlay` / `.modal` / `.field` `.hint` / `.grid-2` / `.check` | формы create/edit | `components.jsx` |
| `pre.conf` (`.cmt` `.kw`) / `.config-pane` / `.result` | превью `proxy.conf`, apply | `ConfigPreview.jsx` |
| `.toast` (`.err`) | флеш-уведомления | `App.jsx` |

## Хвост (§21 CLAUDE.md)

- Формы уже на русском по смыслу не переведены — интерфейс сейчас **англоязычный**
  (проект MVP). При локализации: русские подписи + `.field-hint`, без показа snake_case.
- Диалоги `confirm()` в страницах (`HomeServers.jsx` и др.) — по §21 заменить на
  UI-модалку подтверждения; пока оставлены как MVP-заглушка.
