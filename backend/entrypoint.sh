#!/bin/sh
# Start FreeRADIUS (if its current config validates) then run the panel API.
# FreeRADIUS failing to start must NOT stop the panel — the panel is how you
# fix the config, via an apply that validates and reloads.
set -e

if freeradius -XC >/dev/null 2>&1; then
    freeradius </dev/null >/dev/null 2>&1 && echo "[entrypoint] FreeRADIUS started"
else
    echo "[entrypoint] FreeRADIUS not started (config not valid yet — use the panel to apply)"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
