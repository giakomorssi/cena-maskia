#!/bin/sh
set -e

# Substitute only ${API_URL} in the nginx template, leave all other nginx
# variables ($host, $http_upgrade, $uri, etc.) untouched.
# Set default port if not provided by Railway
export PORT=${PORT:-80}

envsubst '${PORT}' < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

exec "$@"
