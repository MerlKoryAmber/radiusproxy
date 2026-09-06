#!/bin/sh
# Validate the current config and (re)start the FreeRADIUS daemon.
# Used as RADIUS_RELOAD_CMD. Exits non-zero if the config is invalid so the
# panel reports the reload as failed (the apply step already validated, but this
# guards against a race).
set -e
freeradius -XC
pkill freeradius 2>/dev/null || true
sleep 1
freeradius
echo "FreeRADIUS reloaded"
