FROM python:3.12-slim

WORKDIR /app

# FreeRADIUS 3.2 (Debian bookworm ships 3.2.1) runs in this same container so
# the panel fully manages it: writes config into /etc/freeradius/3.0, validates
# with `freeradius -XC`, and reloads. freeradius-ldap = rlm_ldap (AD group gate),
# freeradius-postgresql = rlm_sql (audit log / local group list), freeradius-utils
# = radclient for testing.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        freeradius freeradius-ldap freeradius-postgresql freeradius-utils \
        procps \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY radius-reload.sh /usr/local/bin/radius-reload.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/radius-reload.sh

EXPOSE 8000
# 1812/1813 = RADIUS auth/acct (FreeRADIUS listens when started).
EXPOSE 1812/udp 1813/udp

CMD ["/usr/local/bin/entrypoint.sh"]
