# shellcheck shell=bash
# Fill the panel's .env with host facts the container can't see for itself —
# the host IPs (HOST_ADDRESSES) and the host's real name (HOST_HOSTNAME), shown
# read-only in Settings → Host and used in the self-signed cert SAN.
#
# Idempotent + non-destructive: upserts ONLY these keys, preserving every other
# line (secrets like APP_ENCRYPTION_KEY / JWT_SECRET written by `rpp secrets`).
# Source this; call write_host_env "<install_dir>". Both install.sh and
# update.sh call it, so a plain `rpp update` keeps host info correct with no
# manual .env editing on the server.

# Upsert KEY=VALUE in FILE (replace the line if present, else append). Values
# here are IPs / hostnames — no shell-special chars — so plain rewrite is safe.
env_upsert() {  # env_upsert FILE KEY VALUE
    local file="$1" key="$2" val="$3" tmp
    [ -f "$file" ] || : > "$file"
    if grep -q "^${key}=" "$file" 2>/dev/null; then
        tmp="$(mktemp)"
        grep -v "^${key}=" "$file" > "$tmp"
        printf '%s=%s\n' "$key" "$val" >> "$tmp"
        cat "$tmp" > "$file"
        rm -f "$tmp"
    else
        printf '%s=%s\n' "$key" "$val" >> "$file"
    fi
}

# Host ports the stack publishes. Read from .env (docker compose substitutes the
# same keys in docker-compose.yml); defaults = the classic layout, so prod is
# unchanged. Lets the panel share a host that already uses 80/443/8000/1812
# (e.g. a lab running another 2FA stack). Exports the vars for health checks.
load_ports() {  # load_ports INSTALL_DIR
    local env="$1/.env" kv k v
    for kv in PANEL_HTTP_PORT:80 PANEL_HTTPS_PORT:443 API_PORT:8000 \
              RADIUS_AUTH_PORT:1812 RADIUS_ACCT_PORT:1813; do
        k="${kv%%:*}"
        v="$(sed -n "s/^${k}=//p" "$env" 2>/dev/null | tail -1)"
        export "$k=${v:-${kv#*:}}"
    done
}

write_host_env() {  # write_host_env INSTALL_DIR
    local dir="$1" env="$1/.env" addrs host
    addrs="$(hostname -I 2>/dev/null | tr ' ' ',' | sed 's/,$//')"
    host="$(hostname -f 2>/dev/null || hostname 2>/dev/null || true)"
    env_upsert "$env" HOST_ADDRESSES "$addrs"
    env_upsert "$env" HOST_HOSTNAME "$host"
}
