#!/bin/sh
# Runs from nginx's /docker-entrypoint.d before nginx starts.
# 1) make sure a cert exists (the backend writes the real one to the shared
#    volume; generate a stopgap so nginx can boot if it's not there yet),
# 2) reload nginx in the background whenever the cert changes (cert replace).
set -e
CERT_DIR=/etc/nginx/certs
mkdir -p "$CERT_DIR"

i=0
while [ ! -s "$CERT_DIR/cert.pem" ] && [ "$i" -lt 30 ]; do
    sleep 1
    i=$((i + 1))
done

if [ ! -s "$CERT_DIR/cert.pem" ]; then
    echo "[tls] backend cert not present yet — generating a stopgap"
    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" \
        -days 3650 -subj "/CN=radius-proxy-panel" 2>/dev/null || true
fi

(
    while inotifywait -e close_write,create,move,moved_to "$CERT_DIR" >/dev/null 2>&1; do
        nginx -s reload 2>/dev/null || true
    done
) &
