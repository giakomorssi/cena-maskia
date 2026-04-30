#!/bin/sh
set -e

# Substitute only ${API_URL} in the nginx template, leave all other nginx
# variables ($host, $http_upgrade, $uri, etc.) untouched.
envsubst '${API_URL} ${PORT}' < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

exec "$@"
