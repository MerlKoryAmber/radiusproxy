#!/bin/bash
#
# FreeRADIUS Proxy Panel — host management CLI (`rpp`).
# Interactive numbered menu with no args; the same actions as subcommands.
# Wraps scripts/{install,update,uninstall}.sh + a systemd unit; never
# duplicates their logic. See docs/patterns/cli-menu-linux.md.
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SELF_DIR/lib/common.sh"

_rand() { head -c 32 /dev/urandom | base64 | tr -d '\n=+/' | cut -c1-40; }
_set_env() {  # file KEY VALUE — replace in place or append
    local f="$1" k="$2" v="$3"
    touch "$f"
    if grep -q "^$k=" "$f" 2>/dev/null; then
        sed -i "s|^$k=.*|$k=$v|" "$f"
    else
        printf '%s=%s\n' "$k" "$v" >> "$f"
    fi
}

_health() {
    local ip; ip="$(hostname -I 2>/dev/null | awk '{print $1}')"; ip="${ip:-localhost}"
    echo "  Panel : https://$ip   (self-signed — replace in Settings → TLS)"
    printf '  https : '; curl -sk -o /dev/null -w '%{http_code}\n' https://localhost/ 2>/dev/null || echo down
    printf '  api   : '; curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/health 2>/dev/null || echo down
}

# --- lifecycle -------------------------------------------------------------
cmd_update()         { need_root; cd /tmp; bash "$REPO_ROOT/scripts/update.sh"; }
cmd_update_nopull()  { need_root; cd /tmp; bash "$REPO_ROOT/scripts/update.sh" --no-pull; }
cmd_uninstall()      { need_root; confirm "Uninstall — remove containers/images, KEEP data volume?" || return 1
                       bash "$REPO_ROOT/scripts/uninstall.sh" --keep-data; }
cmd_uninstall_purge(){ need_root; confirm2 "PURGE — delete containers, DATA VOLUMES and the checkout?" || return 1
                       bash "$REPO_ROOT/scripts/uninstall.sh" --purge; }

# --- credentials / secrets -------------------------------------------------
cmd_secrets() {
    need_root
    local env="$REPO_ROOT/.env" do_enc=0 do_jwt=0
    echo "Panel secrets in .env (prod hardening):"
    echo "  APP_ENCRYPTION_KEY — encrypts stored RADIUS/AD secrets at rest."
    echo "  JWT_SECRET         — signs login sessions."
    warn "Rotating APP_ENCRYPTION_KEY makes ALREADY-stored secrets unreadable —"
    warn "only safe on a fresh/empty panel, else you must re-enter every secret."
    if confirm "Set/rotate APP_ENCRYPTION_KEY (random)?"; then
        confirm2 "Existing stored secrets will become unreadable — proceed?" && do_enc=1
    fi
    confirm "Set/rotate JWT_SECRET (random, logs everyone out)?" && do_jwt=1
    [ "$do_enc" = 0 ] && [ "$do_jwt" = 0 ] && { log "no changes."; return 0; }
    [ "$do_enc" = 1 ] && _set_env "$env" APP_ENCRYPTION_KEY "$(_rand)"
    [ "$do_jwt" = 1 ] && _set_env "$env" JWT_SECRET "$(_rand)"
    chmod 600 "$env"
    log "wrote $env — recreating backend to apply…"
    compose up -d --force-recreate backend
    log "done."
}

cmd_password() {
    need_root
    local pw="${RPP_NEW_PASSWORD:-}" pw2
    if [ -z "$pw" ]; then
        pw="$(ask_secret 'New admin password (min 4): ')"
        pw2="$(ask_secret 'Repeat: ')"
        [ "$pw" = "$pw2" ] || die "passwords do not match."
    fi
    [ "${#pw}" -ge 4 ] || die "password too short (min 4)."
    # Password via stdin (never in argv/logs); hashed inside the backend.
    printf '%s' "$pw" | compose exec -T backend python -c '
import sys, asyncio
from sqlalchemy import select
from app.database import SessionLocal
from app import models, auth
pw = sys.stdin.read()
async def main():
    async with SessionLocal() as db:
        u = (await db.execute(select(models.User).where(models.User.username=="admin"))).scalar_one_or_none()
        if u is None:
            db.add(models.User(username="admin", password_hash=auth.hash_password(pw)))
        else:
            u.password_hash = auth.hash_password(pw)
        await db.commit()
asyncio.run(main())
' && log "admin password updated." || die "failed (is the stack running? see: $CLI_NAME status)."
}

cmd_git_token() {
    need_root
    local url clean hostpath pat code
    url="$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null)" || die "no origin remote."
    clean="$(printf '%s' "$url" | sed -E 's#https://[^@/]*@#https://#')"
    echo "Repo (origin): $clean"
    pat="$(ask_secret 'GitHub PAT (input hidden): ')"
    [ -n "$pat" ] || die "empty token."
    # ls-remote alone gives a false OK on public repos — verify the PAT via API.
    code="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $pat" https://api.github.com/user)"
    [ "$code" = "200" ] || die "token rejected by GitHub API (HTTP $code)."
    hostpath="$(printf '%s' "$clean" | sed -E 's#^https://##')"
    git -C "$REPO_ROOT" remote set-url origin "https://x-access-token:${pat}@${hostpath}"
    if git -C "$REPO_ROOT" ls-remote origin >/dev/null 2>&1; then
        log "git token set and verified."
    else
        git -C "$REPO_ROOT" remote set-url origin "$clean"
        die "ls-remote failed — reverted origin to clean URL."
    fi
}

# --- runtime (systemd unit; falls back to compose) -------------------------
_svc() { command -v systemctl >/dev/null 2>&1 && systemctl "$1" "$UNIT" 2>/dev/null; }
cmd_status() {
    echo "Install : $REPO_ROOT"
    echo "Git HEAD: $(git -C "$REPO_ROOT" log --oneline -1 2>/dev/null || echo '?')"
    local ustate="n/a"
    command -v systemctl >/dev/null 2>&1 && ustate="$(systemctl is-active "$UNIT" 2>/dev/null || true)"
    echo "Unit    : ${ustate:-inactive}"
    echo "Containers:"; compose ps 2>/dev/null || warn "compose not available"
    _health
}
cmd_start()   { need_root; _svc start   || compose up -d;   log "started."; }
cmd_stop()    { need_root; confirm "Stop the stack?" || return 1; _svc stop || compose down; log "stopped."; }
cmd_restart() { need_root; confirm "Restart the stack?" || return 1
                _svc restart || { compose down; compose up -d; }; log "restarted."; }

cmd_logs() {
    local n svc
    echo "  1) backend   2) frontend   3) db   4) all"
    n="$(ask 'service [1-4]: ')"
    case "$n" in 1) svc=backend ;; 2) svc=frontend ;; 3) svc=db ;; 4) svc="" ;; *) return 1 ;; esac
    if [ -t 1 ]; then compose logs -f --tail=200 $svc; else compose logs --tail=200 $svc; fi
}

# --- data: backup / restore ------------------------------------------------
cmd_backup() {
    need_root
    local stamp dir
    stamp="$(date +%Y%m%d-%H%M%S)"
    dir="$REPO_ROOT/storage/backup/$stamp"
    mkdir -p "$dir"
    chmod 700 "$REPO_ROOT/storage" "$REPO_ROOT/storage/backup" 2>/dev/null || true
    log "dumping database…"
    compose exec -T db pg_dump -U radpanel -d radpanel --clean --if-exists > "$dir/db.sql" \
        || die "pg_dump failed (is the stack running?)."
    chmod 600 "$dir/db.sql"
    if [ -f "$REPO_ROOT/.env" ]; then cp "$REPO_ROOT/.env" "$dir/.env"; chmod 600 "$dir/.env"; fi
    chmod 700 "$dir"
    log "backup → $dir"
}
cmd_restore() {
    need_root
    local base="$REPO_ROOT/storage/backup"
    [ -d "$base" ] || die "no backups in $base."
    local stamps; mapfile -t stamps < <(ls -1 "$base" 2>/dev/null | sort -r)
    [ "${#stamps[@]}" -gt 0 ] || die "no backups found."
    echo "Backups (newest first):"
    local i=1; for s in "${stamps[@]}"; do printf '  %2d) %s\n' "$i" "$s"; i=$((i+1)); done
    local sel; sel="$(ask 'restore which [number]: ')"
    [[ "$sel" =~ ^[0-9]+$ ]] && [ "$sel" -ge 1 ] && [ "$sel" -le "${#stamps[@]}" ] || die "bad selection."
    local dir="$base/${stamps[$((sel-1))]}"
    [ -f "$dir/db.sql" ] || die "no db.sql in $dir."
    confirm2 "Restore DB from ${stamps[$((sel-1))]} OVER the current database?" || return 1
    compose up -d db >/dev/null 2>&1 || true
    log "restoring database…"
    compose exec -T db psql -U radpanel -d radpanel < "$dir/db.sql" >/dev/null || die "restore failed."
    if [ -f "$dir/.env" ] && confirm "Also restore .env from this backup?"; then
        cp "$dir/.env" "$REPO_ROOT/.env"; chmod 600 "$REPO_ROOT/.env"
        confirm "Restart stack to apply .env?" && cmd_restart
    fi
    log "restore done."
}

# --- self-healing watchdog (ADR-0012) --------------------------------------
# Runs off a systemd timer (every ~1 min). Checks containers + API health; on
# failure escalates restart×2 → rebuild×1 (same commit) → give up + email,
# with a cooldown so it never loops. State is a file on the host (the DB may be
# what is down). "All targets down" is NOT our failure — that is the backend's
# internal loop + mail, not a restart trigger, so the watchdog only heals the
# stack itself.
WD_MAX_RESTART=2
WD_MAX_REBUILD=1
WD_COOLDOWN=1800          # seconds to stay hands-off after giving up
WD_HEALTH_URL="http://localhost:8000/api/health"

# state file: KEY=VALUE lines — phase, restarts, rebuilds, gave_up_at, incident
_wd_get() { [ -f "$WATCHDOG_STATE" ] && sed -n "s/^$1=//p" "$WATCHDOG_STATE" | tail -1 || true; }
_wd_set() {  # _wd_set KEY VALUE
    mkdir -p "$(dirname "$WATCHDOG_STATE")"
    touch "$WATCHDOG_STATE"
    if grep -q "^$1=" "$WATCHDOG_STATE" 2>/dev/null; then
        sed -i "s|^$1=.*|$1=$2|" "$WATCHDOG_STATE"
    else
        printf '%s=%s\n' "$1" "$2" >> "$WATCHDOG_STATE"
    fi
}
_wd_reset() { : > "$WATCHDOG_STATE"; }

# Healthy = every compose service running AND the API answers 200.
_wd_healthy() {
    local bad
    bad="$(compose ps --format '{{.Service}} {{.State}}' 2>/dev/null | grep -vc ' running$' || true)"
    [ "${bad:-1}" = "0" ] || return 1
    [ "$(curl -s -o /dev/null -w '%{http_code}' "$WD_HEALTH_URL" 2>/dev/null)" = "200" ]
}

# Send an alert: prefer the panel's stored SMTP (via backend), else host MTA,
# else just log — the backend's internal loop will mail once it is back up.
_wd_alert() {  # _wd_alert SUBJECT BODY
    local subj="$1" body="$2"
    if compose exec -T backend python -m app.send_alert "$subj" <<<"$body" >/dev/null 2>&1; then
        return 0
    fi
    if command -v sendmail >/dev/null 2>&1; then
        printf 'Subject: %s\n\n%s\n' "$subj" "$body" | sendmail -t 2>/dev/null && return 0
    fi
    warn "watchdog: could not send alert ($subj)"
    return 1
}

cmd_watchdog() {
    need_root
    # Serialize: overlapping timer runs must not stack.
    exec 9>"${WATCHDOG_STATE}.lock" 2>/dev/null || true
    flock -n 9 2>/dev/null || { log "watchdog: another run in progress — skipping this tick"; return 0; }

    if _wd_healthy; then
        # Recovered? announce once, then clear state.
        if [ -n "$(_wd_get incident)" ]; then
            _wd_alert "[RADIUS] Panel recovered" "The panel stack is healthy again ($(date '+%F %T %z'))." || true
            log "watchdog: recovered — state cleared"
        fi
        _wd_reset
        return 0
    fi

    # Unhealthy. Respect cooldown after a give-up.
    local phase gave_up now
    phase="$(_wd_get phase)"; phase="${phase:-none}"
    gave_up="$(_wd_get gave_up_at)"; now="$(date +%s)"
    if [ "$phase" = "gaveup" ]; then
        if [ -n "$gave_up" ] && [ "$((now - gave_up))" -lt "$WD_COOLDOWN" ]; then
            return 0   # hands-off window; human was already emailed
        fi
        _wd_reset; phase="none"   # cooldown elapsed — allow a fresh cycle
    fi

    [ -n "$(_wd_get incident)" ] || { _wd_set incident "$now"; _wd_set restarts 0; _wd_set rebuilds 0
        _wd_alert "[RADIUS] Panel unhealthy" "Watchdog detected the stack is down/unhealthy ($(date '+%F %T %z')). Attempting automatic recovery." || true; }

    local restarts rebuilds
    restarts="$(_wd_get restarts)"; restarts="${restarts:-0}"
    rebuilds="$(_wd_get rebuilds)"; rebuilds="${rebuilds:-0}"

    if [ "$restarts" -lt "$WD_MAX_RESTART" ]; then
        restarts=$((restarts+1)); _wd_set restarts "$restarts"; _wd_set phase "restart"
        log "watchdog: restart attempt $restarts/$WD_MAX_RESTART"
        _wd_alert "[RADIUS] Watchdog: restarting stack" "Restart attempt $restarts/$WD_MAX_RESTART ($(date '+%F %T %z'))." || true
        compose restart >/dev/null 2>&1 || { compose down >/dev/null 2>&1; compose up -d >/dev/null 2>&1; }
        return 0   # next timer tick re-checks health
    fi

    if [ "$rebuilds" -lt "$WD_MAX_REBUILD" ]; then
        rebuilds=$((rebuilds+1)); _wd_set rebuilds "$rebuilds"; _wd_set phase "rebuild"
        log "watchdog: rebuild attempt $rebuilds/$WD_MAX_REBUILD (same commit)"
        _wd_alert "[RADIUS] Watchdog: rebuilding stack" "Restarts did not help — rebuilding the SAME commit $rebuilds/$WD_MAX_REBUILD ($(date '+%F %T %z')). This can take minutes." || true
        compose up -d --build >/dev/null 2>&1 || true   # same checkout, NO git pull
        return 0
    fi

    # Exhausted — stop touching the stack, escalate to a human, start cooldown.
    _wd_set phase "gaveup"; _wd_set gave_up_at "$now"
    log "watchdog: exhausted restart+rebuild — escalating to human"
    _wd_alert "[RADIUS] Panel STILL down — manual action needed" \
        "Automatic recovery failed after $WD_MAX_RESTART restart(s) and $WD_MAX_REBUILD rebuild(s) ($(date '+%F %T %z')). The watchdog will stay hands-off for $((WD_COOLDOWN/60)) min. Please investigate: sudo rpp status; sudo rpp logs." || true
}

cmd_url()  { _health; }
cmd_help() {
    cat <<HELP
$CLI_NAME — FreeRADIUS Proxy Panel host CLI ($REPO_ROOT)

  (no args)         interactive menu
  update            git pull + rebuild
  update-nopull     rebuild without pulling
  uninstall         remove containers/images, keep data volume
  uninstall-purge   remove everything incl. data volume + checkout
  secrets           set APP_ENCRYPTION_KEY / JWT_SECRET (.env)
  password          reset the admin password
  git-token         set a GitHub PAT on origin (private repo)
  status            install path, git HEAD, unit, containers, health
  start|stop|restart  control the stack (systemd unit)
  logs              tail service logs
  backup            dump DB + .env to storage/backup/<stamp>/
  restore           restore DB (and optionally .env) from a backup
  watchdog          one self-heal check (run by the systemd timer; ADR-0012)
  url               panel URL + health
  help              this text
HELP
}

# --- menu ------------------------------------------------------------------
show_menu() {
    local g="$C_ACCENT" o="$C_OFF"
    printf '\n  %sRADIUS PROXY PANEL%s  (%s)\n' "$g" "$o" "$REPO_ROOT"
    cat <<M
————————————————————————————————
  ${g} 0.${o} Exit
————————————————————————————————
  ${g} 1.${o} Update (git pull + rebuild)
  ${g} 2.${o} Update without pull
  ${g} 3.${o} Uninstall (keep data)
  ${g} 4.${o} Uninstall + volumes (PURGE)
————————————————————————————————
  ${g} 5.${o} Set encryption / JWT secrets
  ${g} 6.${o} Reset admin password
  ${g} 7.${o} Set git token (private repo)
————————————————————————————————
  ${g} 8.${o} Status
  ${g} 9.${o} Start stack
  ${g}10.${o} Stop stack
  ${g}11.${o} Restart stack
  ${g}12.${o} Logs
————————————————————————————————
  ${g}13.${o} Backup DB + config
  ${g}14.${o} Restore from backup
  ${g}15.${o} Panel URL / health
  ${g}16.${o} Watchdog: run a self-heal check now
————————————————————————————————
M
}

run_menu() {
    need_root
    while true; do
        show_menu
        local n; n="$(ask 'Please enter your selection [0-16]: ')"
        case "$n" in
            0)  exit 0 ;;
            1)  cmd_update || true ;;
            2)  cmd_update_nopull || true ;;
            3)  cmd_uninstall || true ;;
            4)  cmd_uninstall_purge || true ;;
            5)  cmd_secrets || true ;;
            6)  cmd_password || true ;;
            7)  cmd_git_token || true ;;
            8)  cmd_status || true ;;
            9)  cmd_start || true ;;
            10) cmd_stop || true ;;
            11) cmd_restart || true ;;
            12) cmd_logs || true ;;
            13) cmd_backup || true ;;
            14) cmd_restore || true ;;
            15) cmd_url || true ;;
            16) cmd_watchdog || true ;;
            *)  echo "Please enter the correct number [0-16]" ;;
        esac
        _pause
    done
}

case "${1:-}" in
    "")               run_menu ;;
    help|-h|--help)   cmd_help ;;
    update)           cmd_update ;;
    update-nopull)    cmd_update_nopull ;;
    uninstall)        cmd_uninstall ;;
    uninstall-purge)  cmd_uninstall_purge ;;
    secrets)          cmd_secrets ;;
    password)         cmd_password ;;
    git-token)        cmd_git_token ;;
    status)           cmd_status ;;
    start)            cmd_start ;;
    stop)             cmd_stop ;;
    restart)          cmd_restart ;;
    logs)             cmd_logs ;;
    backup)           cmd_backup ;;
    restore)          cmd_restore ;;
    watchdog)         cmd_watchdog ;;
    url)              cmd_url ;;
    *)                echo "Unknown command: $1 (try: $CLI_NAME help)" >&2; exit 1 ;;
esac
