#!/usr/bin/env bash
#
# FreeRADIUS Proxy Panel — uninstaller. Tears down the stack.
#   sudo /opt/radiusproxy/scripts/uninstall.sh [--purge] [--keep-data]
#
# By default: stops containers, removes the panel's built images and its DB
# volume (panel data is lost). Docker Engine itself is NOT removed.
#   --keep-data   keep the Postgres volume (config/audit survive a reinstall)
#   --purge       also delete the checkout directory
#
# Config via env: INSTALL_DIR (default: repo root — parent of this scripts/ dir)
set -euo pipefail

log()  { printf '\033[1;36m[uninstall]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[uninstall] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root (sudo)."

PURGE=0; KEEP_DATA=0
for a in "$@"; do
    case "$a" in
        --purge) PURGE=1 ;;
        --keep-data) KEEP_DATA=1 ;;
        *) die "unknown option: $a" ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${INSTALL_DIR:-$(dirname "$SCRIPT_DIR")}"
COMPOSE="$INSTALL_DIR/docker-compose.yml"

[ -f "$COMPOSE" ] || die "no docker-compose.yml at $INSTALL_DIR (set INSTALL_DIR)."

if [ "$KEEP_DATA" -eq 1 ]; then
    log "stopping stack, removing built images (keeping data volume)…"
    docker compose -f "$COMPOSE" down --rmi local
else
    log "stopping stack, removing built images AND data volumes…"
    docker compose -f "$COMPOSE" down -v --rmi local
fi

# Remove the host CLI wrapper + systemd unit (subshell: keep our log()).
( INSTALL_DIR="$INSTALL_DIR" . "$SCRIPT_DIR/lib/common.sh"; remove_unit; remove_cli ) \
    && log "removed host CLI (rpp) + systemd unit" || true

if [ "$PURGE" -eq 1 ]; then
    log "removing checkout $INSTALL_DIR…"
    rm -rf "$INSTALL_DIR"
fi

log "done. Docker Engine was left installed."
