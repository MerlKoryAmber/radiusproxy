#!/usr/bin/env bash
#
# rehydrate — старт сессии агента ОДНИМ вызовом (CLAUDE.md §23).
# Вместо десятка ls/git/чтений: git-срез, версии, верх handoff + хвосты,
# состояние графа graphify, доступ к лабе, карта docs. Только чтение.
#
#   bash tools/rehydrate.sh            # с git fetch
#   bash tools/rehydrate.sh --no-fetch # офлайн
#
# Работает в Linux и в Git Bash на Windows.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
FETCH=1
[ "${1:-}" = "--no-fetch" ] && FETCH=0

h() { printf '\n=== %s ===\n' "$*"; }

# Печать секции markdown от заголовка до следующего заголовка того же уровня.
section() {  # section FILE "## Заголовок"
    awk -v start="$2" '
        index($0, start) == 1 { on = 1; print; next }
        on && /^## / { exit }
        on { print }
    ' "$1"
}

# --- git ---------------------------------------------------------------------
h "git"
[ "$FETCH" -eq 1 ] && git fetch origin --prune -q 2>/dev/null
branch="$(git branch --show-current)"
echo "ветка: $branch"
if git rev-parse -q --verify origin/main >/dev/null; then
    read -r behind ahead < <(git rev-list --left-right --count origin/main...HEAD)
    echo "vs origin/main: отстаём на $behind, впереди на $ahead$([ "$FETCH" -eq 0 ] && echo ' (без fetch)')"
fi
dirty="$(git status --short)"
if [ -n "$dirty" ]; then echo "незакоммичено:"; echo "$dirty" | sed 's/^/  /'; else echo "дерево чистое"; fi
echo "последние коммиты:"; git log --oneline -5 | sed 's/^/  /'
unmerged="$(git for-each-ref --format='%(refname:short)' refs/heads refs/remotes/origin \
    | grep -v -e '^main$' -e '^origin/main$' -e '^origin/HEAD$' -e '^origin$' \
    | while read -r b; do n="$(git rev-list --count "main..$b" 2>/dev/null || echo 0)"; [ "$n" -gt 0 ] && echo "  $b (+$n не в main)"; done)"
[ -n "$unmerged" ] && { echo "ветки с коммитами вне main (§7):"; echo "$unmerged"; }
stash="$(git stash list)"
[ -n "$stash" ] && { echo "stash (чужие не pop'ать, §7):"; echo "$stash" | sed 's/^/  /'; }

# --- версии ------------------------------------------------------------------
h "версии"
echo "frontend: $(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' frontend/package.json | head -1)"
echo "CHANGELOG верх: $(grep -m1 '^### ' CHANGELOG.md | sed 's/^### //')"
echo "последний ADR: $(ls docs/adr | grep -E '^[0-9]{4}-' | tail -1)"

# --- handoff -----------------------------------------------------------------
HO=docs/handoff/CURRENT.md
if [ -f "$HO" ]; then
    h "handoff: верх"
    awk 'NR>1 && /^---$/ { exit } { print }' "$HO"
    h "handoff: хвосты"
    section "$HO" "## Хвосты"
    h "handoff: не делать"
    section "$HO" "## Не делать"
    h "handoff: старт следующего агента"
    section "$HO" "## Старт следующего агента"
fi

# --- graphify ----------------------------------------------------------------
h "graphify"
if ! command -v graphify >/dev/null 2>&1; then
    echo "CLI нет → pip install \"graphifyy==$(cat .claude/skills/graphify/.graphify_version 2>/dev/null)\""
elif [ ! -f graphify-out/graph.json ]; then
    echo "графа нет → graphify update .   (AST, ~5 c, без ключей)"
else
    mtime() { date -r "$1" +%s 2>/dev/null || stat -c %Y "$1"; }
    gtime="$(mtime graphify-out/graph.json)"
    ctime="$(git log -1 --format=%ct)"
    nodes="$(grep -o '"id":' graphify-out/graph.json | wc -l | tr -d ' ')"
    state="актуален"
    # Устарел, если после сборки графа был коммит или правился код.
    newer=0
    [ "$ctime" -gt "$gtime" ] && newer=1
    while read -r f; do
        [ -f "$f" ] && [ "$(mtime "$f")" -gt "$gtime" ] && { newer=1; break; }
    done < <(git status --short -- '*.py' '*.js' '*.jsx' '*.sh' | awk '{print $NF}')
    [ "$newer" -eq 1 ] && state="устарел → graphify update ."
    echo "граф: ~$nodes узлов, $state"
    echo "git-хуки авто-обновления:"
    graphify hook status 2>/dev/null | sed 's/^/  /'
fi

# --- лаба --------------------------------------------------------------------
h "лаба 192.168.0.178"
key="$HOME/.ssh/radiusproxy_ed25519"
if [ -f "$key" ]; then echo "ключ есть: $key"; else echo "ключа НЕТ: $key — SSH на лабу с этой машины не выйдет"; fi
cfg="$HOME/.ssh/config"
if [ -f "$cfg" ] && [ "$(head -c3 "$cfg" | od -An -tx1 | tr -d ' ')" = "efbbbf" ]; then
    echo "~/.ssh/config с BOM — ssh его не читает (пересохранить без BOM)"
fi

# --- карта docs --------------------------------------------------------------
h "docs"
find docs -name '*.md' | sort | sed 's/^/  /'
echo
echo "дальше: docs/SKELETON.md (§22), вопросы по коду — graphify query/explain"
