# FreeRADIUS Proxy Panel

A web panel for managing **RADIUS request proxying** in FreeRADIUS 3.2.x. It is
a focused editor for `proxy.conf` — home servers, pools, and realms — with
live config preview, validation via `freeradius -XC`, and a safe apply that
rolls back on error. Backend is FastAPI, frontend is React (Vite).

This is an MVP scaffold meant to be extended, not a finished product. See
[Security](#security) before putting it anywhere near production.

## The core idea

RADIUS proxying in FreeRADIUS 3.2 is configured **in files, not in SQL**. The
routing lives in `proxy.conf` as three block types:

| Block               | What it is                                             |
|---------------------|--------------------------------------------------------|
| `home_server`       | An upstream RADIUS server (ip, port, secret, type)     |
| `home_server_pool`  | A group of home servers + a load-balancing strategy    |
| `realm`             | A routing rule: which pool handles a User-Name suffix  |

So FreeRADIUS itself needs **no database** for proxying. This panel keeps its
**own** database — home servers, pools, realms, and an audit log — and renders
that into a valid `proxy.conf` on demand. All FreeRADIUS-specific syntax lives
in one module (`backend/app/radius_config.py`), so the renderer can be swapped
without touching the API or data model.

### Request flow

```
        User-Name: bob@example.com
                 │
                 ▼
   ┌──────────────────────────┐     realm example.com  ──►  pool "isp_pool"
   │   FreeRADIUS (proxy)      │                                   │
   │   reads proxy.conf        │                       fail-over / load-balance
   └──────────────────────────┘                                   │
                 │                                    ┌────────────┴───────────┐
                 ▼                                    ▼                        ▼
          this panel writes                     home_server rad1         home_server rad2
          & reloads proxy.conf                  10.0.0.11:1812           10.0.0.12:1812
```

## FreeRADIUS version

Targets the current stable line, **3.2.x** (tested against 3.2.5 / 3.2.10),
which uses the classic `proxy.conf` model.

> **FreeRADIUS 4 note:** v4 removed `proxy.conf` entirely — `realm`,
> `home_server`, and `home_server_pool` no longer exist and proxying is done
> with `rlm_radius` module instances instead. This panel does **not** target v4.
> When you migrate, replace only `radius_config.py`; the data model still maps
> cleanly onto per-home-server module instances.

## Project layout

> **Актуальная карта проекта — `docs/SKELETON.md`** (файлы/роли, модель, эндпоинты,
> рендереры), живой срез и «старт следующего агента» — `docs/handoff/CURRENT.md`,
> архитектурные решения — `docs/adr/` (реестр `docs/adr/README.md`). Этот README —
> обзор; при расхождении верить SKELETON/коду.

```
freeradius-panel/
├── docker-compose.yml         # db + backend(+FreeRADIUS 3.2) + frontend(nginx, HTTPS)
├── scripts/                   # install.sh / update.sh / uninstall.sh + rpp.sh (host CLI)
├── backend/app/
│   ├── radius_config.py       # ★ весь FreeRADIUS-синтаксис: рендер + validate/apply/rollback
│   ├── models.py              # TargetServer / Pool / Client / Rule / Ldap/Tls/Auth / Audit
│   ├── portable.py            # импорт/экспорт портируемого JSON (миграция NPS, ADR-0007)
│   ├── tls.py crypto.py auth.py ldap_sync.py   # HTTPS-серт / шифрование секретов / вход / AD-синк
│   ├── schemas.py crud.py database.py main.py routers/
│   └── requirements.txt
└── frontend/src/
    ├── pages/                 # Dashboard/Clients/TargetServers/Pools/Rules/Decisions/Config/Portable/Settings
    ├── api.js  App.jsx  components.jsx
```

## Running it

### Option A — Docker (Postgres) — co-located FreeRADIUS

FreeRADIUS 3.2 runs **inside** the backend container; the panel writes real
`/etc/freeradius/3.0`, validates with `freeradius -XC` and reloads it.

```bash
docker compose up -d --build
```

- Panel UI: **<https://localhost>** (self-signed cert — browser warns; replace in Settings → TLS)
- Backend API + docs: <http://localhost:8000/docs>
- RADIUS: `:1812/udp` (auth), `:1813/udp` (acct)
- Login is OFF by default (open); default admin `admin` / `admin`.

### Option A2 — Production install on a Linux host

```bash
curl -fsSL https://raw.githubusercontent.com/MerlKoryAmber/radiusproxy/main/scripts/install.sh | sudo bash
```

Installs Docker + compose + git, clones to `/opt/radiusproxy`, brings the stack up,
and installs the host CLI **`rpp`** (`sudo rpp` → menu: update / status / logs /
backup / restore / password / secrets / …). Prod: set strong secrets with
`rpp secrets` and replace the cert in Settings → TLS.

**Behind a proxy (no direct `docker.io`)?** The docker daemon is a systemd
service and won't see a proxy exported in your shell, so image pulls time out
(`dial tcp registry-1.docker.io:443: i/o timeout`). `install.sh`/`update.sh`
auto-pick a proxy from the environment or `/etc/environment` and configure the
daemon + builds for it. If `sudo` strips your env, pass it explicitly:

```bash
curl -fsSL https://raw.githubusercontent.com/MerlKoryAmber/radiusproxy/main/scripts/install.sh \
  | sudo DOCKER_HTTP_PROXY=http://HOST:PORT bash
```

The running containers stay proxy-free on purpose (they reach LDAP/RADIUS
directly); only pulls/builds use the proxy. Disable with `DOCKER_PROXY_SKIP=1`.

### Option B — Local dev (SQLite, no database to set up)

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload            # http://localhost:8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev                              # http://localhost:5173
```

The Vite dev server proxies `/api` to `http://localhost:8000`.

## Wiring up validate + apply

By default the panel just **writes** `proxy.conf` — validation and reload are
opt-in so the panel can run off-host safely. To enable them, the panel must run
somewhere it can write FreeRADIUS's config and run its CLI:

```bash
# in backend/.env
PROXY_CONF_PATH=/etc/freeradius/3.0/proxy.conf   # Debian/Ubuntu path
RADIUS_CHECK_CMD=freeradius -XC                   # dry-run parse before apply
RADIUS_RELOAD_CMD=systemctl reload freeradius     # reload after a good apply
```

On apply the panel backs up the current file, writes the new one, runs
`freeradius -XC`, and **rolls back to the backup if validation fails** — so a
broken config never reaches the running server. Reload only runs after a pass.

Config paths by distro: Debian/Ubuntu `/etc/freeradius/3.0/`, RHEL/CentOS
`/etc/raddb/`.

## API

| Method | Path                    | Purpose                                  |
|--------|-------------------------|------------------------------------------|
| GET/POST/PUT/DELETE | `/api/home-servers` | Manage home servers          |
| GET/POST/PUT/DELETE | `/api/pools`        | Manage pools + ordered members |
| GET/POST/PUT/DELETE | `/api/realms`       | Manage realms                |
| GET    | `/api/config/preview`   | Rendered `proxy.conf` (JSON)             |
| GET    | `/api/config/preview.conf` | Rendered `proxy.conf` (raw text)      |
| POST   | `/api/config/apply`     | Write + validate + reload (422 on invalid) |
| GET    | `/api/config/audit`     | Recent change / apply log                |

Interactive docs at `/docs`.

## Security

This MVP has **no authentication** and manages **shared secrets in plaintext**.
Before any real use:

- Put it behind authentication (the audit log already records an `actor` field).
- Serve over HTTPS only; never expose the API publicly unauthenticated.
- Restrict who can run the apply/reload commands.
- Consider encrypting secrets at rest.

## Next steps

- Auth (the `actor` field in the audit log is ready for it)
- Alembic migrations (models currently auto-create on startup)
- An audit-log UI page (endpoint already exists)
- Live home-server status via FreeRADIUS `status-server`
- A FreeRADIUS 4 renderer behind the same API
```
