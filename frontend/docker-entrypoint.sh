#!/bin/sh
set -e

# Get DNS resolver from /etc/resolv.conf.
# nginx requires IPv6 addresses wrapped in brackets: [addr]
# Try IPv4 first; if none found, use the first nameserver (IPv6) with brackets.
IPV4_DNS=$(awk '/^nameserver/ && $2 ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ {print $2; exit}' /etc/resolv.conf)
if [ -n "$IPV4_DNS" ]; then
    export DNS_RESOLVER="$IPV4_DNS"
else
    RAW_DNS=$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf)
    export DNS_RESOLVER="[${RAW_DNS}]"
fi

# Set default port if not provided by Railway
export PORT=${PORT:-80}

envsubst '${PORT} ${DNS_RESOLVER}' < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

exec "$@"
