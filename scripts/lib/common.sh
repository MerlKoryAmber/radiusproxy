# shellcheck shell=bash
# Shared helpers for the FreeRADIUS Proxy Panel host scripts (rpp menu +
# install/update/uninstall). Source this; do not execute it.
#
# Provides: REPO_ROOT / COMPOSE / CLI_NAME / ETC_DIR / UNIT resolution,
# log/warn/die, need_root, compose(), confirm()/confirm2(), ask()/ask_secret(),
# ensure_cli()/remove_cli(), ensure_unit()/remove_unit().

CLI_NAME="rpp"
ETC_DIR="/etc/rpp"
UNIT="radiusproxy.service"

# --- repo root -------------------------------------------------------------
# Prefer the recorded path (survives being called via /usr/bin/rpp); else
# derive from this file's location (…/scripts/lib/common.sh → repo root).
if [ -f "$ETC_DIR/repo_root" ]; then
    REPO_ROOT="$(cat "$ETC_DIR/repo_root")"
else
    _self="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    REPO_ROOT="${INSTALL_DIR:-$_self}"
fi
COMPOSE="$REPO_ROOT/docker-compose.yml"

# --- output ----------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    C_ACCENT=$'\033[0;32m'; C_WARN=$'\033[1;33m'; C_ERR=$'\033[1;31m'; C_OFF=$'\033[0m'
else
    C_ACCENT=""; C_WARN=""; C_ERR=""; C_OFF=""
fi
log()  { printf '%s[rpp]%s %s\n' "$C_ACCENT" "$C_OFF" "$*"; }
warn() { printf '%s[rpp]%s %s\n' "$C_WARN" "$C_OFF" "$*"; }
die()  { printf '%s[rpp] ERROR:%s %s\n' "$C_ERR" "$C_OFF" "$*" >&2; exit 1; }

need_root() { [ "$(id -u)" -eq 0 ] || die "run as root (sudo $CLI_NAME)."; }

DOCKER="$(command -v docker || echo /usr/bin/docker)"
compose() { "$DOCKER" compose -f "$COMPOSE" "$@"; }

# --- interaction (works under agents/pipes: /dev/tty if usable, else stdin) --
_read() {  # _read VAR PROMPT [-s]
    local __var="$1" __prompt="$2" __silent="${3:-}" __src=/dev/stdin
    if printf '' >/dev/tty 2>/dev/null; then __src=/dev/tty; fi
    if [ "$__silent" = "-s" ]; then
        read -r -s -p "$__prompt" "$__var" <"$__src" >/dev/tty 2>&1 || true
        printf '\n' >/dev/tty 2>/dev/null || true
    else
        read -r -p "$__prompt" "$__var" <"$__src" || true
    fi
}
ask()        { local v; _read v "$1"; printf '%s' "$v"; }
ask_secret() { local v; _read v "$1" -s; printf '%s' "$v"; }

confirm() {  # confirm "prompt" → 0 if yes
    local ans; _read ans "${1:-Proceed?} [y/N]: "
    case "$ans" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}
confirm2() {  # two confirms for destructive actions
    confirm "$1" || return 1
    confirm "Are you SURE? this cannot be undone [y/N]: " || return 1
    return 0
}
_pause() { local x; _read x "  — press Enter —"; }

# --- host CLI wrapper (/usr/bin/rpp → scripts/rpp.sh from the tree) ---------
ensure_cli() {
    mkdir -p "$ETC_DIR"
    printf '%s\n' "$REPO_ROOT" > "$ETC_DIR/repo_root"
    chmod 644 "$ETC_DIR/repo_root"
    local wrap="/usr/bin/$CLI_NAME"
    cat > "$wrap" <<'WRAP'
#!/bin/bash
# FreeRADIUS Proxy Panel host CLI — thin wrapper. Logic lives in the repo tree,
# so a git pull always refreshes the menu.
set -euo pipefail
ROOT="$(cat /etc/rpp/repo_root 2>/dev/null || true)"
[ -n "$ROOT" ] && [ -f "$ROOT/scripts/rpp.sh" ] || {
    echo "rpp: repo not found (see /etc/rpp/repo_root)" >&2; exit 1; }
exec bash "$ROOT/scripts/rpp.sh" "$@"
WRAP
    chmod 0755 "$wrap"
    install -m 0755 "$wrap" "/usr/local/bin/$CLI_NAME" 2>/dev/null || true
}
remove_cli() {
    rm -f "/usr/bin/$CLI_NAME" "/usr/local/bin/$CLI_NAME"
    rm -f "$ETC_DIR/repo_root"; rmdir "$ETC_DIR" 2>/dev/null || true
}

# --- systemd unit (oneshot compose up/down) --------------------------------
ensure_unit() {
    command -v systemctl >/dev/null 2>&1 || { warn "no systemd — skipping unit."; return 0; }
    cat > "/etc/systemd/system/$UNIT" <<UNITF
[Unit]
Description=FreeRADIUS Proxy Panel (docker compose stack)
Requires=docker.service
After=docker.service network-online.target
[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$REPO_ROOT
ExecStart=$DOCKER compose -f $COMPOSE up -d
ExecStop=$DOCKER compose -f $COMPOSE down
[Install]
WantedBy=multi-user.target
UNITF
    systemctl daemon-reload
    systemctl enable "$UNIT" >/dev/null 2>&1 || true
}
remove_unit() {
    command -v systemctl >/dev/null 2>&1 || return 0
    systemctl disable "$UNIT" >/dev/null 2>&1 || true
    rm -f "/etc/systemd/system/$UNIT"
    systemctl daemon-reload 2>/dev/null || true
}
