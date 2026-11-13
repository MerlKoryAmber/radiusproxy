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

write_host_env() {  # write_host_env INSTALL_DIR
    local dir="$1" env="$1/.env" addrs host
    addrs="$(hostname -I 2>/dev/null | tr ' ' ',' | sed 's/,$//')"
    host="$(hostname -f 2>/dev/null || hostname 2>/dev/null || true)"
    env_upsert "$env" HOST_ADDRESSES "$addrs"
    env_upsert "$env" HOST_HOSTNAME "$host"
}
