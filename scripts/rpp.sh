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
    echo "Unit    : $(command -v systemctl >/dev/null 2>&1 && systemctl is-active "$UNIT" 2>/dev/null || echo n/a)"
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
  url               panel URL + health
  help              this text
HELP
}

# --- menu ------------------------------------------------------------------
show_menu() {
    printf '\n  %sRADIUS PROXY PANEL%s  (%s)\n' "$C_ACCENT" "$C_OFF" "$REPO_ROOT"
    cat <<M
————————————————————————————————
   0. Exit
————————————————————————————————
   1. Update (git pull + rebuild)
   2. Update without pull
   3. Uninstall (keep data)
   4. Uninstall + volumes (PURGE)
————————————————————————————————
   5. Set encryption / JWT secrets
   6. Reset admin password
   7. Set git token (private repo)
————————————————————————————————
   8. Status
   9. Start stack
  10. Stop stack
  11. Restart stack
  12. Logs
————————————————————————————————
  13. Backup DB + config
  14. Restore from backup
  15. Panel URL / health
————————————————————————————————
M
}

run_menu() {
    need_root
    while true; do
        show_menu
        local n; n="$(ask 'Please enter your selection [0-15]: ')"
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
            *)  echo "Please enter the correct number [0-15]" ;;
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
    url)              cmd_url ;;
    *)                echo "Unknown command: $1 (try: $CLI_NAME help)" >&2; exit 1 ;;
esac
