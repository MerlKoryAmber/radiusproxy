#!/bin/sh
# Validate the current config and (re)start the FreeRADIUS daemon.
# Used as RADIUS_RELOAD_CMD. Exits non-zero if the config is invalid so the
# panel reports the reload as failed.
#
# IMPORTANT: the daemon's stdio is detached to /dev/null. The panel captures
# this script's stdout via a pipe; if the backgrounded daemon inherited that
# pipe it would hold it open and the panel's read would block forever.
set -e
freeradius -XC
pkill -x freeradius 2>/dev/null || true
sleep 1
freeradius </dev/null >/dev/null 2>&1
echo "FreeRADIUS reloaded"
