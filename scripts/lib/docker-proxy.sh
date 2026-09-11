# shellcheck shell=bash
# Teach the Docker daemon (and image builds) to use the host's HTTP proxy.
#
# WHY: dockerd is a systemd service and does NOT inherit your shell/login env,
# so a proxy you exported in your session is invisible to `docker pull` — the
# base images (postgres, python, node, nginx) then time out reaching docker.io
# (the classic `dial tcp registry-1.docker.io:443: i/o timeout`). We resolve a
# proxy from the environment (or /etc/environment) and, when one is found:
#   1. write a systemd drop-in so the daemon uses it for image pulls, and
#   2. export the standard vars so `docker compose build` forwards them to
#      apt-get / npm inside the build (Compose passes them through as build args
#      — see docker-compose.yml `build.args`).
#
# Runtime proxying of the containers stays OFF on purpose (docker-compose.yml
# blanks http_proxy/no_proxy in each service `environment:`) — FreeRADIUS and
# the panel must reach LDAP/RADIUS peers directly, not via any proxy. This file
# only touches the *build/pull* path.
#
# Source this file (do not execute); then call apply_docker_proxy.
#
# Env knobs:
#   DOCKER_HTTP_PROXY / DOCKER_HTTPS_PROXY / DOCKER_NO_PROXY  force explicit values
#   DOCKER_PROXY_SKIP=1                                       skip entirely (no-op)

_dp_say()  { printf '\033[1;36m[proxy]\033[0m %s\n' "$*"; }
_dp_warn() { printf '\033[1;33m[proxy]\033[0m %s\n' "$*" >&2; }

# Read one KEY from /etc/environment (pam_env `KEY=value` format), strip quotes.
_dp_envfile() {  # _dp_envfile VAR
    [ -f /etc/environment ] || return 0
    sed -n "s/^[[:space:]]*$1=//p" /etc/environment | tail -n1 \
        | sed 's/^"//; s/"$//; s/^'\''//; s/'\''$//'
}

apply_docker_proxy() {
    [ "${DOCKER_PROXY_SKIP:-0}" = "1" ] && { _dp_say "DOCKER_PROXY_SKIP=1 — leaving docker as-is."; return 0; }

    local http https no
    # precedence: explicit DOCKER_*_PROXY > standard *_PROXY env
    http="${DOCKER_HTTP_PROXY:-${HTTP_PROXY:-${http_proxy:-}}}"
    https="${DOCKER_HTTPS_PROXY:-${HTTPS_PROXY:-${https_proxy:-}}}"
    no="${DOCKER_NO_PROXY:-${NO_PROXY:-${no_proxy:-}}}"
    # fall back to /etc/environment (sudo/pipe often strips the caller's env)
    if [ -z "$http" ] && [ -z "$https" ]; then
        http="$(_dp_envfile HTTP_PROXY)";  [ -n "$http" ]  || http="$(_dp_envfile http_proxy)"
        https="$(_dp_envfile HTTPS_PROXY)"; [ -n "$https" ] || https="$(_dp_envfile https_proxy)"
        [ -n "$no" ] || { no="$(_dp_envfile NO_PROXY)"; [ -n "$no" ] || no="$(_dp_envfile no_proxy)"; }
    fi
    # mirror a single value across both schemes
    [ -n "$https" ] || https="$http"
    [ -n "$http" ]  || http="$https"

    if [ -z "$http" ] && [ -z "$https" ]; then
        _dp_warn "no HTTP proxy found in env or /etc/environment — docker left unchanged."
        _dp_warn "if image pulls time out, re-run with an explicit proxy, e.g.:"
        _dp_warn "    sudo DOCKER_HTTP_PROXY=http://HOST:PORT bash scripts/install.sh"
        return 0
    fi

    # never proxy the local stack / loopback (append to any caller-supplied list)
    local base="localhost,127.0.0.1,::1,db,backend,frontend,.local"
    if [ -n "$no" ]; then no="$no,$base"; else no="$base"; fi

    # 1) image PULLS — systemd drop-in for the docker daemon
    if command -v systemctl >/dev/null 2>&1; then
        local dir=/etc/systemd/system/docker.service.d
        local file="$dir/http-proxy.conf" new
        mkdir -p "$dir"
        new="[Service]
Environment=\"HTTP_PROXY=$http\"
Environment=\"HTTPS_PROXY=$https\"
Environment=\"NO_PROXY=$no\"
Environment=\"http_proxy=$http\"
Environment=\"https_proxy=$https\"
Environment=\"no_proxy=$no\""
        if [ ! -f "$file" ] || [ "$(cat "$file" 2>/dev/null)" != "$new" ]; then
            printf '%s\n' "$new" > "$file"
            systemctl daemon-reload
            systemctl restart docker || _dp_warn "docker restart failed — proxy may not apply."
            _dp_say "docker daemon proxy set + restarted: $http"
        else
            systemctl is-active --quiet docker || systemctl start docker || true
            _dp_say "docker daemon proxy already current: $http"
        fi
    else
        _dp_warn "no systemd — set the docker daemon proxy manually (image pulls need it)."
    fi

    # 2) image BUILDS — Compose forwards these to apt-get / npm as build args
    export HTTP_PROXY="$http" HTTPS_PROXY="$https" NO_PROXY="$no"
    export http_proxy="$http" https_proxy="$https" no_proxy="$no"
}
