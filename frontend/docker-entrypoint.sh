#!/bin/sh
set -e

# Get the first IPv4 DNS resolver from the system (IPv6 breaks nginx resolver syntax)
DNS_RESOLVER=$(awk '/^nameserver/ && $2 ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ {print $2; exit}' /etc/resolv.conf)
export DNS_RESOLVER=${DNS_RESOLVER:-8.8.8.8}

# Set default port if not provided by Railway
export PORT=${PORT:-80}

envsubst '${PORT} ${DNS_RESOLVER}' < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

exec "$@"
