#!/usr/bin/env bash
#
# FreeRADIUS Proxy Panel — installer.
#
# Installs the panel and everything it needs to run on a fresh Linux host:
#   - Docker Engine + the compose plugin (if missing)
#   - git (if missing)
#   - clones the repo and brings the stack up (panel + FreeRADIUS + Postgres)
#
# Standalone-safe: you can run it straight from a checkout, or pipe it in:
#   curl -fsSL https://raw.githubusercontent.com/MerlKoryAmber/radiusproxy/main/scripts/install.sh | sudo bash
#
# Config via env:
#   REPO_URL     git repo (default: MerlKoryAmber/radiusproxy)
#   BRANCH       branch to deploy (default: main)
#   INSTALL_DIR  where to clone (default: /opt/radiusproxy)
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/MerlKoryAmber/radiusproxy.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/radiusproxy}"

log()  { printf '\033[1;36m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[install]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[install] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root (sudo)."

# --- detect package manager -------------------------------------------------
if command -v dnf >/dev/null 2>&1; then PKG=dnf
elif command -v yum >/dev/null 2>&1; then PKG=yum
elif command -v apt-get >/dev/null 2>&1; then PKG=apt
else die "unsupported distro: need dnf, yum or apt-get."; fi

ensure_git() {
    command -v git >/dev/null 2>&1 && return
    log "installing git…"
    case "$PKG" in
        dnf|yum) "$PKG" -y install git ;;
        apt) apt-get update -qq && apt-get install -y git ;;
    esac
}

ensure_docker() {
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        log "docker + compose already present ($(docker --version | awk '{print $3}' | tr -d ,))."
        systemctl enable --now docker >/dev/null 2>&1 || true
        return
    fi
    log "installing Docker Engine + compose plugin…"
    case "$PKG" in
        dnf|yum)
            "$PKG" -y install dnf-plugins-core || "$PKG" -y install yum-utils || true
            if command -v dnf >/dev/null 2>&1; then
                dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            else
                yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            fi
            "$PKG" -y install docker-ce docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin
            ;;
        apt)
            apt-get update -qq
            apt-get install -y ca-certificates curl gnupg
            install -m 0755 -d /etc/apt/keyrings
            local codename id
            . /etc/os-release; id="$ID"; codename="${VERSION_CODENAME:-}"
            curl -fsSL "https://download.docker.com/linux/${id}/gpg" \
                -o /etc/apt/keyrings/docker.asc
            chmod a+r /etc/apt/keyrings/docker.asc
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${id} ${codename} stable" \
                > /etc/apt/sources.list.d/docker.list
            apt-get update -qq
            apt-get install -y docker-ce docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin
            ;;
    esac
    systemctl enable --now docker
}

clone_or_update() {
    if [ -d "$INSTALL_DIR/.git" ]; then
        log "updating existing checkout at $INSTALL_DIR…"
        git -C "$INSTALL_DIR" fetch --all --prune
        git -C "$INSTALL_DIR" checkout "$BRANCH"
        git -C "$INSTALL_DIR" pull --ff-only
    else
        log "cloning $REPO_URL → $INSTALL_DIR (branch $BRANCH)…"
        git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    fi
}

wait_healthy() {
    log "waiting for the panel to come up…"
    for _ in $(seq 1 60); do
        if curl -fsSk -o /dev/null https://localhost/ 2>/dev/null \
           && curl -fsS -o /dev/null http://localhost:8000/api/health 2>/dev/null; then
            return 0
        fi
        sleep 3
    done
    warn "panel did not report healthy in time — check: docker compose -f $INSTALL_DIR/docker-compose.yml logs"
    return 1
}

write_env() {
    # Host IPs shown read-only in the panel (the container can't see host NICs).
    local addrs
    addrs="$(hostname -I 2>/dev/null | tr ' ' ',' | sed 's/,$//')"
    printf 'HOST_ADDRESSES=%s\n' "$addrs" > "$INSTALL_DIR/.env"
}

ensure_git
ensure_docker
clone_or_update
write_env

log "building and starting the stack (this can take a few minutes)…"
docker compose -f "$INSTALL_DIR/docker-compose.yml" up -d --build

# Install the host CLI (`rpp`) + systemd unit (subshell: don't clobber our log()).
( INSTALL_DIR="$INSTALL_DIR" . "$INSTALL_DIR/scripts/lib/common.sh"; ensure_cli; ensure_unit ) \
    && log "host CLI installed: rpp (menu) — try: sudo rpp" || warn "rpp CLI install skipped"

wait_healthy || true

ip="$(hostname -I 2>/dev/null | awk '{print $1}')"; ip="${ip:-<host-ip>}"
cat <<DONE

$(printf '\033[1;32m[install] FreeRADIUS Proxy Panel is up.\033[0m')

  Panel UI : https://${ip}   (self-signed cert — browser will warn; replace it in Settings → TLS)
  API      : http://${ip}:8000
  RADIUS   : ${ip}:1812/udp (auth), ${ip}:1813/udp (acct)
  Install  : ${INSTALL_DIR}

  Panel login is OFF by default (open). Default admin: admin / admin —
  change it (top-right user menu) and enable login in Settings before prod.
  Restrict access by IP in Settings → Access if needed.

  Firewall (if enabled): open 80,443/tcp and 1812-1813/udp, e.g.
    firewall-cmd --add-service=http --add-service=https --add-port=1812-1813/udp --permanent && firewall-cmd --reload

  Manage    : sudo rpp            (menu: update / status / logs / backup / restore / password / …)
  Update    : sudo rpp update     (or ${INSTALL_DIR}/scripts/update.sh)
  Uninstall : sudo rpp uninstall  (or ${INSTALL_DIR}/scripts/uninstall.sh)
DONE
