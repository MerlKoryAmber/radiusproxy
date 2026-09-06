#!/usr/bin/env bash
#
# FreeRADIUS Proxy Panel — updater. Pulls the latest code and rebuilds the stack.
#   sudo /opt/radiusproxy/scripts/update.sh
#
# Config via env:
#   BRANCH       branch to deploy (default: main)
#   INSTALL_DIR  checkout location (default: dir of this script's parent)
set -euo pipefail

log()  { printf '\033[1;36m[update]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[update] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root (sudo)."

BRANCH="${BRANCH:-main}"
# Default INSTALL_DIR = repo root (parent of this scripts/ dir).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${INSTALL_DIR:-$(dirname "$SCRIPT_DIR")}"

[ -d "$INSTALL_DIR/.git" ] || die "no git checkout at $INSTALL_DIR (set INSTALL_DIR)."

log "updating $INSTALL_DIR (branch $BRANCH)…"
git -C "$INSTALL_DIR" fetch --all --prune
git -C "$INSTALL_DIR" checkout "$BRANCH"
git -C "$INSTALL_DIR" pull --ff-only

log "rebuilding and restarting…"
docker compose -f "$INSTALL_DIR/docker-compose.yml" up -d --build

log "waiting for health…"
for _ in $(seq 1 60); do
    if curl -fsSk -o /dev/null https://localhost/ 2>/dev/null \
       && curl -fsS -o /dev/null http://localhost:8000/api/health 2>/dev/null; then
        log "panel is up."
        exit 0
    fi
    sleep 3
done
die "panel did not report healthy — check: docker compose -f $INSTALL_DIR/docker-compose.yml logs"
